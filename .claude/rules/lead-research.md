# AI lead research (weekly research bot)

A weekly routine where Claude searches the web for new hotel openings, retail
launches and QSR expansions in our markets and proposes them as leads. It only
proposes: a person approves each lead in the CRM before anything is created,
and nothing is emailed by the routine.

## Pieces

| Piece | Where |
|-------|-------|
| Models | `LeadResearchRun`, `ResearchLead` (`crm_app/models.py`, migration `0106_lead_research`) |
| Research + approve/reject | `crm_app/services/lead_research_service.py` |
| Cron command | `python manage.py research_new_venues` |
| API | `/api/v1/research-leads/` (list, `approve`, `reject`, `pending_count`), `/api/v1/lead-research-runs/` |
| Review page | `/research-leads` (`ResearchLeads.tsx`), Sales menu "AI lead research" |

## How a run works

- Model `claude-opus-5-5` (override with `LEAD_RESEARCH_MODEL`) with the
  `web_search_20260209` server tool and one strict client tool, `record_lead`,
  that Claude calls once per lead. Server-side refusal fallback is on.
- The prompt carries the qualification rules (hotels 50+ rooms 3-star+, fashion
  flagships/5+ stores, QSR 10+ outlets), Beat Breeze as the default product,
  and an EXCLUDE list of recent proposals and the newest CRM companies.
- Stored leads must have a source URL. Emails are kept only when they look like
  a published business address; the prompt forbids guessed addresses.
- Dedupe: normalised venue name + city against leads from the last 180 days,
  and venues whose company already has an active opportunity are skipped.

## Approving a lead

`approve_lead()` creates (or reuses) the company, adds a contact only when the
lead has a published email, creates an opportunity (`stage=Contacted`,
`lead_source='AI Research'`, value = zones x 290 or 400), a follow-up task, and
then calls `ProspectEnrollmentService.auto_enroll_new_opportunity` after commit.
Without an email the task asks staff to find the decision maker and no sequence
starts. Approve/reject need a person on the website (`WritesOnWebsite`); API
tokens and agents may read the queue only.

## Switches and rollout

- `LEAD_RESEARCH_ENABLED` (default off). With it off the command exits at once;
  `--dry-run` prints leads and saves nothing, `--force` runs once without the flag.
- Needs `ANTHROPIC_API_KEY` (already used by `ai_service.py`).
- The cron is not created by code: add a Render cron (Singapore) running
  `python manage.py research_new_venues` weekly, e.g. Monday 01:00 UTC (08:00 Bangkok).
- Each run is up to 4 web searches per requested lead (60 for 15) plus tokens; `LeadResearchRun` records
  searches and token counts per run.

## Outreach after approval

Approved leads with an email are enrolled through the existing prospect
sequences, whose `ai_email` steps wait in AI Email Drafts for approval. The
prospect-sequence cron was disabled on 30 Mar 2026 (see `render.yaml`), so the
first step only runs once that cron is on again or another sender (Lyra) picks
up `lead_source='AI Research'` opportunities.
