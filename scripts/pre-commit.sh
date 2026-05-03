#!/usr/bin/env bash
# pre-commit hook: warn if a file listed in LOCAL_PATCHES.md is being
# committed without a [LOCAL] prefix in the commit subject.
#
# To install: cp scripts/pre-commit.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit

set -u

# Files mentioned in LOCAL_PATCHES.md table (under "Active patches")
PATCHED_FILES=$(awk '/^## Active patches$/,/^## /{ if($0 ~ /^\| `[^`]+`/) { match($0, /`[^`]+\.(py|md|js|ts|json|yml|yaml|toml|ini)`/); if(RSTART) print substr($0, RSTART+1, RLENGTH-2) } }' LOCAL_PATCHES.md 2>/dev/null)

[ -z "$PATCHED_FILES" ] && exit 0

STAGED=$(git diff --cached --name-only)

HITS=""
for f in $PATCHED_FILES; do
    if echo "$STAGED" | grep -qxF "$f"; then
        HITS+="  - $f"$'\n'
    fi
done

[ -z "$HITS" ] && exit 0

# Compose commit msg can be checked via .git/COMMIT_EDITMSG, but on pre-commit
# the subject is not yet written. We can only warn here; commit-msg hook
# enforces the prefix.
echo "[pre-commit] WARNING: editing files registered in LOCAL_PATCHES.md:"
echo "$HITS"
echo "Make sure your commit subject starts with [LOCAL] or you may break"
echo "the verify_local_patches.py guarantee on future rebases."

exit 0
