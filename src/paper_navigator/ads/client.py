"""NASA ADS Search API client.

Verified against official sources on 2026-11-12:
* Base URL ``https://api.adsabs.harvard.edu/v1``, endpoint ``/search/query``,
  header ``Authorization: Bearer <token>`` (github.com/adsabs/adsabs-dev-api README).
* ``rows`` default 10, maximum 2000; ``start`` is the 0-based offset
  (adsabs-dev-api ``openapi/parameters.yaml``).
* Rate-limit headers ``X-RateLimit-Limit/Remaining/Reset`` (reset = UTC epoch seconds);
  standard limit 5000 requests/day (https://adsabs.github.io/help/policies/rate-limits).

The token is only ever placed in the request header and is never logged or stored.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

from ..errors import ErrorCode, PNError
from ..records import PaperRecord
from .mapping import ADS_FIELDS, ads_doc_to_record

log = logging.getLogger(__name__)

MAX_ROWS = 2000
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_BACKOFF_SECONDS = 60.0


@dataclass
class RateLimit:
    limit: int | None = None
    remaining: int | None = None
    reset_epoch: int | None = None


@dataclass
class SearchPage:
    num_found: int
    start: int
    docs: list[dict[str, Any]]


@dataclass
class SearchResult:
    query: str
    records: list[PaperRecord] = field(default_factory=list)
    num_found: int | None = None
    pages: int = 0
    error: PNError | None = None
    skipped: int = 0
    stopped_by_limit: bool = False
    paging: list[dict[str, int]] = field(default_factory=list)

    @property
    def fetched(self) -> int:
        return len(self.records)

    @property
    def complete(self) -> bool:
        """True only when every matching record was retrieved without error."""
        return (
            self.error is None
            and self.num_found is not None
            and self.fetched + self.skipped >= self.num_found
        )


class ADSClient:
    def __init__(
        self,
        token: str,
        base_url: str = "https://api.adsabs.harvard.edu/v1",
        timeout: float = 30.0,
        max_retries: int = 3,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if not token:
            raise PNError(ErrorCode.CONFIG_ERROR, "ADS token is empty")
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            transport=transport,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
        self.max_retries = max_retries
        self._sleep = sleep
        self.requests_made = 0
        self.rate_limit = RateLimit()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ADSClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- low level -----------------------------------------------------------------
    def _update_rate_limit(self, resp: httpx.Response) -> None:
        def _h(name: str) -> int | None:
            v = resp.headers.get(name)
            try:
                return int(v) if v is not None else None
            except ValueError:
                return None

        rl = RateLimit(
            _h("X-RateLimit-Limit"), _h("X-RateLimit-Remaining"), _h("X-RateLimit-Reset")
        )
        if rl.limit is not None or rl.remaining is not None:
            self.rate_limit = rl

    def _retry_delay(self, attempt: int, resp: httpx.Response | None) -> float:
        if resp is not None:
            ra = resp.headers.get("Retry-After")
            if ra:
                try:
                    return min(float(ra), MAX_BACKOFF_SECONDS)
                except ValueError:
                    pass
        return min(2.0**attempt, MAX_BACKOFF_SECONDS)

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        last_exc: PNError | None = None
        for attempt in range(self.max_retries + 1):
            resp: httpx.Response | None = None
            try:
                self.requests_made += 1
                resp = self._client.get(path, params=params)
            except httpx.TimeoutException:
                last_exc = PNError(ErrorCode.TIMEOUT, f"ADS request timed out ({path})")
            except httpx.TransportError as exc:
                last_exc = PNError(ErrorCode.NETWORK_ERROR, f"{type(exc).__name__} ({path})")
            else:
                self._update_rate_limit(resp)
                status = resp.status_code
                if status == 200:
                    try:
                        data = resp.json()
                    except (json.JSONDecodeError, ValueError) as exc:
                        raise PNError(ErrorCode.INVALID_RESPONSE, "response is not JSON") from exc
                    if not isinstance(data, dict):
                        raise PNError(ErrorCode.INVALID_RESPONSE, "response is not a JSON object")
                    return data
                if status in (401, 403):
                    raise PNError(ErrorCode.AUTH_ERROR, f"HTTP {status} from ADS")
                if status == 400:
                    raise PNError(
                        ErrorCode.INPUT_ERROR,
                        f"ADS rejected the query (HTTP 400): {resp.text[:200]}",
                    )
                if status == 404:
                    raise PNError(ErrorCode.INVALID_RESPONSE, f"ADS endpoint not found ({path})")
                if status == 429:
                    last_exc = PNError(
                        ErrorCode.RATE_LIMITED,
                        "HTTP 429 from ADS",
                        retry_after=self._retry_delay(attempt, resp),
                    )
                    if self.rate_limit.remaining == 0:
                        break  # daily quota exhausted: retrying now will not help
                elif status in RETRYABLE_STATUS:
                    last_exc = PNError(ErrorCode.NETWORK_ERROR, f"HTTP {status} from ADS")
                else:
                    raise PNError(ErrorCode.INVALID_RESPONSE, f"unexpected HTTP {status}")
            if attempt < self.max_retries:
                delay = self._retry_delay(attempt, resp)
                log.warning(
                    "ADS request failed (%s); retry %d/%d in %.1fs",
                    last_exc.code if last_exc else "?",
                    attempt + 1,
                    self.max_retries,
                    delay,
                )
                self._sleep(delay)
        assert last_exc is not None
        raise last_exc

    def search_page(
        self,
        q: str,
        start: int = 0,
        rows: int = 50,
        sort: str = "bibcode asc",
        fields: list[str] | None = None,
    ) -> SearchPage:
        rows = max(1, min(rows, MAX_ROWS))
        data = self._get(
            "/search/query",
            {
                "q": q,
                "fl": ",".join(fields or ADS_FIELDS),
                "rows": rows,
                "start": start,
                "sort": sort,
            },
        )
        response = data.get("response")
        if not isinstance(response, dict):
            raise PNError(ErrorCode.INVALID_RESPONSE, "missing 'response' object")
        docs = response.get("docs")
        num_found = response.get("numFound")
        if not isinstance(docs, list) or not isinstance(num_found, int):
            raise PNError(ErrorCode.INVALID_RESPONSE, "missing 'docs' or 'numFound'")
        return SearchPage(num_found=num_found, start=start, docs=docs)

    # -- high level -----------------------------------------------------------------
    def search(
        self,
        q: str,
        max_results: int = 50,
        page_size: int = 200,
        sort: str = "bibcode asc",
        request_budget: Callable[[], bool] | None = None,
    ) -> SearchResult:
        """Fetch up to ``max_results`` records, paging with ``start``/``rows``.

        Errors after at least one page yield a partial result (``error`` set) instead of
        raising, so callers can keep what was retrieved. Errors on the first page raise.
        """
        result = SearchResult(query=q)
        start = 0
        while True:
            if request_budget is not None and not request_budget():
                result.stopped_by_limit = True
                break
            rows = min(page_size, max_results - result.fetched - result.skipped, MAX_ROWS)
            if rows <= 0:
                result.stopped_by_limit = (
                    result.num_found is not None
                    and result.fetched + result.skipped < result.num_found
                )
                break
            try:
                page = self.search_page(q, start=start, rows=rows, sort=sort)
            except PNError as exc:
                if result.pages == 0:
                    raise
                result.error = exc
                break
            result.pages += 1
            result.num_found = page.num_found
            result.paging.append({"start": start, "rows": rows, "returned": len(page.docs)})
            for doc in page.docs:
                try:
                    rec = ads_doc_to_record(doc)
                except TypeError:
                    result.skipped += 1
                    continue
                if not rec.bibcode:
                    result.skipped += 1  # cannot be identified or linked; never invent one
                    continue
                result.records.append(rec)
            start += len(page.docs)
            if not page.docs or start >= page.num_found:
                break
        return result
