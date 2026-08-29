# Local patches on top of upstream

Patches that live ONLY in this fork. Never get pushed back to BEDOLAGA-DEV
(at least not from the [LOCAL] commits — they may be PR'd separately).

Each patch must include a unique marker comment in the source. After every
`git rebase upstream/main`, run `python3 scripts/verify_local_patches.py`.
If the marker is missing, the patch was silently dropped or upstream
overwrote it — investigate before continuing.

## Active patches

| File | Marker | Purpose |
|---|---|---|
| `app/cabinet/routes/subscription_modules/devices.py` | `[LOCAL-PATCH] only enforce 1ruble floor when there is something to charge` | Don't force `max(100, 0) = 100` kopeks when `chargeable_devices == 0` (free-within-tariff quota). Without this, cabinet `/devices/purchase` returns 402 with "1₽ required" while UI shows "free". |
| `app/services/guest_purchase_service.py` | `[LOCAL-PATCH] yookassa-api-reconcile` | Self-heal lost YooKassa webhooks. `recover_stuck_pending_purchases` only sees local rows a webhook already marked succeeded; when the webhook is never delivered the row stays `pending` and the guest never gets a key. Pre-pass polls the YooKassa API for stuck PENDING yookassa purchases and mirrors the webhook effect onto the local row, then the tested amount-verified recovery/fulfillment path takes over. Idempotent, best-effort. |
| `app/services/remnawave_service.py` | `[LOCAL-PATCH] multitariff-sync-dedup-guard` | Nightly full multi-tariff sync crashed daily at 06:00 (UniqueViolationError on uq_subscriptions_user_tariff_active, whole batch rolled back): create-path deduped only by remnawave_id (empty on bot-purchased subs) and never checked for an existing active sub of the same tariff before INSERT. Fix: dedup also by panel shortUuid + skip creation when an active/trial/limited sub with same tariff_id exists. |

## Conventions

- Every commit that adds/edits a local patch must have `[LOCAL]` prefix in
  the commit subject. Example:
  `[LOCAL] cabinet/devices: don't force 1ruble floor when chargeable_devices is 0`
- Include the marker comment directly above the patched line(s).
- Update this table when adding/removing a patch.
- After upstream merge of an equivalent fix, drop the [LOCAL] commit
  (and the marker) on the next rebase.
