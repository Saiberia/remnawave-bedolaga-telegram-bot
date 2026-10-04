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
| `app/services/remnawave_service.py` | `[LOCAL-PATCH] sync-no-deactivate-live-panel-user` | Full sync disabled paid subscriptions (status=disabled, end_date kept, short_uuid/url wiped) for users whose panel account was ACTIVE but had no telegramId while the bot user had lost remnawave_id (29.08.2026, 8 subs). Fix: do not deactivate when any subscription still points to a live panel account by shortUuid or panel id. |
| `app/services/panel_sync/identity.py` | `[LOCAL-PATCH] renewal-takes-over-dead-sibling-panel-account` | Renewal of a live subscription failed with `PanelAccountOwnedByAnotherUser` when the panel account was held by a dead (expired/disabled) sibling row of the SAME user with the SAME shortUuid (2026-10-04, user 731: paid, panel stayed EXPIRED). Fix: in multi-tariff, `find_foreign_panel_owner` releases `remnawave_id` of such a dead sibling (flush only) so the live row takes the account. Any doubt (different user/shortUuid, holder alive, target not alive) keeps the old loud refusal. |
| `app/cabinet/routes/subscription_modules/purchase.py` | `[LOCAL-PATCH] purchase-ids-before-panel-sync` | After a failed panel sync the service rolls back and `subscription.id` becomes an expired attribute -> `MissingGreenlet` (cart not saved, admin notification lost). Ids are captured before the sync. |

## Conventions

- Every commit that adds/edits a local patch must have `[LOCAL]` prefix in
  the commit subject. Example:
  `[LOCAL] cabinet/devices: don't force 1ruble floor when chargeable_devices is 0`
- Include the marker comment directly above the patched line(s).
- Update this table when adding/removing a patch.
- After upstream merge of an equivalent fix, drop the [LOCAL] commit
  (and the marker) on the next rebase.
