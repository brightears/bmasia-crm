# Static synthetic candidate probe

Run this command from this directory.

```sh
python3 probe_candidate.py --candidate /absolute/path/to/pinned-candidate --output candidate_static_assessment.json
BMASIA_COMPAI_SOURCE=/absolute/path/to/pinned-candidate python3 -m unittest discover -s tests -v
```

The probe reads source files and fixed fake records only.

The probe does not start the candidate application.

The probe does not prove API, database, authorization, migration, or integration behavior.

Clone the candidate separately and check out the exact commit in `ASSESSMENT.md`.
No clone, package installation, app start or network call is performed by the probe.
Candidate tests explicitly skip when `BMASIA_COMPAI_SOURCE` is not configured.
