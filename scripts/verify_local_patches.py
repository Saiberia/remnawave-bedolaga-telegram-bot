#!/usr/bin/env python3
"""Verify that all [LOCAL] patches survive after an upstream rebase.

For every entry in PATCHES, check:
  1. The file exists.
  2. The marker substring is present in the file.

Exit code 0 — all good.
Exit code 1 — at least one patch is missing/broken.

Usage: python3 scripts/verify_local_patches.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# (relative-path-to-file, marker-substring)
# Marker MUST be unique enough not to appear elsewhere in the codebase.
PATCHES: list[tuple[str, str]] = [
    (
        'app/cabinet/routes/subscription_modules/devices.py',
        '[LOCAL-PATCH] only enforce 1ruble floor when there is something to charge',
    ),
    (
        'app/services/guest_purchase_service.py',
        '[LOCAL-PATCH] yookassa-api-reconcile',
    ),
    (
        'app/services/remnawave_service.py',
        '[LOCAL-PATCH] multitariff-sync-dedup-guard',
    ),
]

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    errors: list[str] = []
    ok: list[str] = []
    for rel_path, marker in PATCHES:
        path = REPO_ROOT / rel_path
        if not path.is_file():
            errors.append(f'MISSING FILE: {rel_path} (marker: {marker!r})')
            continue
        text = path.read_text(encoding='utf-8')
        if marker not in text:
            errors.append(f'PATCH DROPPED in {rel_path}: marker {marker!r} missing')
        else:
            ok.append(f'{rel_path}: ok')

    for line in ok:
        print(f'  [ok] {line}')
    for line in errors:
        print(f'  [FAIL] {line}', file=sys.stderr)

    if errors:
        print(f'\n{len(errors)} patch(es) broken — DO NOT BUILD until resolved.', file=sys.stderr)
        return 1

    print(f'\nAll {len(PATCHES)} local patch(es) intact.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
