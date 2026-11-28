# Win-back agent (churned customers)

Finds customers who left, has Claude draft a personal come-back email, sends only
after a person approves it, learns why they left, and writes a 5-step improvement plan.

## Pieces

| Piece | Where |
|------|-------|
| Models | `WinBackCandidate`, `ChurnInsightReport` (`crm_app/models.py`, migration `0106_winback`) |
| Logic | `crm_app/services/winback_service.py` |
| API | `crm_app/winback_views.py`: `/api/v1/winback-candidates/` (`scan`, `draft`, `approve`, `skip`, `feedback`, `outcome`, `summary`) and `/api/v1/churn-insights/` (`generate`) |
| Page | `bmasia-crm-frontend/src/pages/WinBack.tsx` at `/win-back` (Sales menu, Sales and Admin roles) |
| Cron-friendly command | `python manage.py winback_scan [--product beatbreeze] [--draft] [--limit 20] [--dry-run]` |
| Replies | `reply_detection_service._record_winback_reply` (runs inside `check_prospect_replies`) |

## Rules

- **Nothing sends without a person.** `approve_and_send` is the only sender, and the
  `approve` action needs the Sales/Admin role plus `PersonSignedInToWebsite` (no API
  tokens, no agent accounts). Drafting, scanning and the command never send.
- Churn = latest recurring contract Expired / Cancelled / `lifecycle_type='churn'` inside
  the window (default 183 days), and no Active/Sent contract running today and no Draft
  starting in the last 60 days or later (a renewal already in progress). One-offs are
  excluded. Expired contracts that were really renewed show as `Renewed`, not here.
- Claude sees only the facts in `build_context()`: name, industry, country, product,
  zones, tenure, last value, how it ended, ticket counts by category, offline-alert
  count, contact name/title/language. Never notes, ticket text or other emails.
- Model: `WINBACK_AI_MODEL` (default `claude-opus-5-5`) with structured JSON output and
  server-side refusal fallback. Needs `ANTHROPIC_API_KEY` and `anthropic>=2.14`.
- Default offer: `WINBACK_DEFAULT_OFFER` ("2 months free when they sign a new 12-month
  plan", chosen by Norbert 28 Nov 2026). The reviewer can change it per draft.
- Sender line: `WINBACK_SENDER_NAME` / `WINBACK_SENDER_TITLE`; optional `WINBACK_REPLY_TO`.
  Replies are only auto-captured when they land in the mailbox `check_prospect_replies`
  reads (`PROSPECT_REPLY_EMAIL`).
