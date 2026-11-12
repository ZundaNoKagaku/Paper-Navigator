#!/usr/bin/env bash
# Fetch the official AASTeX distribution (AAS GitHub: AASJournals/AASTeX7) into
# vendor/aastex/ WITHOUT modifying any file. vendor/ is git-ignored.
#
# Note (checked 2026-11-12): journals.aas.org/authors/aastex.html lists AASTeX v7.0.2
# (2026-06-01) and recommends aasjournalv7.1.bst for v7+, while the GitHub repository's
# latest commit provides v7.0.1 (aastex701.cls, aasjournalv7.bst). If you can reach the
# AAS site, prefer downloading the latest ZIP there and placing its files in vendor/aastex/.
set -euo pipefail
cd "$(dirname "$0")/.."
DEST=vendor/aastex
REF="${AASTEX_REF:-a22d7494854b19aa1141fa9d35a896e7e1f5a6a8}"   # pinned commit (v7.0.1)
rm -rf "$DEST.tmp"
git clone --quiet https://github.com/AASJournals/AASTeX7.git "$DEST.tmp"
git -C "$DEST.tmp" checkout --quiet "$REF"
mkdir -p "$DEST"
cp "$DEST.tmp"/*.cls "$DEST.tmp"/*.bst "$DEST.tmp"/LICENSE "$DEST/"
git -C "$DEST.tmp" log -1 --format='source=https://github.com/AASJournals/AASTeX7 commit=%H date=%cI' > "$DEST/SOURCE.txt"
rm -rf "$DEST.tmp"
( cd "$DEST" && sha256sum *.cls *.bst > SHA256SUMS )
echo "AASTeX files installed in $DEST:"; ls "$DEST"; cat "$DEST/SOURCE.txt"
