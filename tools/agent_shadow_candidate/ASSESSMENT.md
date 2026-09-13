# Synthetic static compatibility assessment

Candidate commit: `6d4793dd6d7aeea91aa6a034e00b17d7408a2d08`.

The probe verifies the pinned commit and a clean candidate Git worktree before it uses `verified_static`.

The probe records a SHA-256 digest of the inspected Prisma schema and router source files.

The probe blocks Company, Contact, and Activity labels when the commit, clean worktree, fixture links, mapped fields, or required routes drift.

The probe uses fixed fake BMAsia records only.

The probe performs an in-memory representative projection and recovery check.

The probe starts no application.

The probe installs no package.

The probe uses no network.

The probe creates no live record.

| BMAsia record | Required static evidence | Result rule |
| --- | --- | --- |
| Company | `Company` fields and `POST /companies`, `PATCH /companies/{id}` | Verified only when every gate passes. |
| Contact | `Contact` fields and `POST /contacts`, `PATCH /contacts/{id}` | Verified only when every gate passes. |
| Activity | `Activity` fields and `POST /activities`, `PATCH /activities/{id}/complete` | Verified only when every gate passes. |
| Contract | `Contract` Prisma model | Missing static support when absent. |
| Invoice | `Invoice` Prisma model | Missing static support when absent. |
| Zone | `Zone` Prisma model | Missing static support when absent. |

This result does not prove running application behavior.

## Issues

1. NOT DONE — Contract support is absent from the inspected candidate schema.
   Fix: retain BMAsia contract handling outside the candidate during shadow work.
2. NOT DONE — Invoice support is absent from the inspected candidate schema.
   Fix: retain BMAsia invoice handling outside the candidate during shadow work.
3. NOT DONE — Zone support is absent from the inspected candidate schema.
   Fix: retain BMAsia zone handling outside the candidate during shadow work.
4. UNKNOWN — Running application behavior is not tested.
   Fix: run a synthetic application test when the team selects that stage.
