# Mail capture: operator runbook

This runbook covers how to stop, the first supervised run, the outcomes and exit codes, how to remove test data,
and the settings. Nothing in this app runs by itself: there is no cron. Every command below is started by a person,
and on production each one needs a go-ahead first.

The examples use `test-mailbox@example.com`. Replace it with the address of the test mailbox made for this
purpose. Never use a real person's mailbox for the first runs.

## How to stop

Any of these stops capture. They are listed from the widest to the narrowest.

- **Everything at once:** set `GOOGLE_CAPTURE_ENABLED` to false on the capture service. From the next command on,
  every form prints `capture disabled: GOOGLE_CAPTURE_ENABLED is off` and exits 0, before any credential or client
  is made. The switch does not interrupt a run already in progress.
- **One mailbox:** untick `enabled` on its row in the admin. The change is written to the access log. Or add the
  address to `GOOGLE_CAPTURE_NEVER_MAILBOXES`, which wins over the table.
- **No credential at all:** set `GOOGLE_CAPTURE_CREDENTIALS_MODE` to `off`.
- **Ctrl-C:** safe at any point. The cursor only moves together with a finished page, the lease is released, and
  the run row stays `running`.

## 0. Before the first run

### Where commands run

Every command in this runbook runs on the **capture service**, as a one-off job or in a shell on that service. It
is never the web service: the web service does not get the capture settings.

**Always pass `--mailbox`.** A reading form without `--mailbox` is refused (exit 2) unless `--all-mailboxes` is
given on purpose, so a run never reads every enabled mailbox by omission.

### Google side (super admin)

- the service account;
- domain-wide delegation for exactly `https://www.googleapis.com/auth/gmail.metadata`;
- for keyless mode, the workload identity pool and provider, and Service Account Token Creator for the federated
  principal on the service account;
- one test mailbox made for this purpose, holding only test mail.

### Settings, in this order (names in section 6)

1. `GOOGLE_CAPTURE_NEVER_MAILBOXES`: every mailbox that must never be read, for example the owner's, HR's and
   finance's. Set this first.
2. `GOOGLE_CAPTURE_CREDENTIALS_MODE` and `GOOGLE_CAPTURE_SERVICE_ACCOUNT`, or the key secret file and
   `GOOGLE_CAPTURE_KEY_FILE`.
3. `CAPTURE_INTERNAL_DOMAINS`: our own mail domains.
4. `GOOGLE_CAPTURE_ENABLED=true`: set this last.

### The mailbox row

1. In the admin, under Mail capture → Capture mailboxes, add `test-mailbox@example.com`, with `enabled` ticked and
   `body_mode` left at headers only.
2. Filter the list on `enabled = yes`. **Only the test mailbox may be listed.** Domain-wide delegation can read any
   mailbox in the domain, so a mistyped real address in a mailbox row would read a real person's mail.

### The self-check

This runs on synthetic fixtures, is rolled back, and makes no Gmail call:

```
python manage.py mail_capture_selfcheck
```

It must report the switch state you expect and a passing pipeline.

## 1. The first supervised run, in this order

Run each step only after the one before it looked right. Send one or two test messages to the test mailbox
**before step 1**, so the backfill in steps 2 and 3 has something to read. `<yesterday>` is yesterday's date,
written `YYYY-MM-DD`.

### Step 1: check the credential

```
python manage.py gmail_sync --check --mailbox test-mailbox@example.com
echo "exit code $?"
```

This costs 1 quota unit and stores nothing but its access-log row.

- **Expect exactly two lines and exit code 0:**

  ```
  enabled mailboxes: test-mailbox@example.com
  test-mailbox@example.com: messages N, history id H
  ```

  The first line lists every enabled mailbox from the table without reading any of them. If it names anything but
  the test mailbox, stop and untick the others.

  The second line proves the delegation, the credential path (keyless signBlob, or the key file) and the scope.
- **Look at:**
  - Admin → Mailbox access logs: one row with purpose `check`, `api_calls` 1 and `finished_at` set.
  - The exit code (section 3).
- **If it says `auth_error <code>: <hint>`** (exit 3), the hint names the setup step to fix: the delegation entry,
  the scope, the service account id, the Token Creator role, or the API not being enabled. Fix that on the Google
  side and repeat step 1. The next good token clears the problem by itself.

### Step 2: see what would be read

```
python manage.py gmail_sync --backfill --since <yesterday> --dry-run --max-messages 20 --mailbox test-mailbox@example.com
echo "exit code $?"
```

This reads and counts, and stores no mail.

- **Expect:** `test-mailbox@example.com: ok ...`, with counts such as `fetched=1` and `matched=1`, and exit code 0.
- **Look at:**
  - Admin → Capture runs: the newest row has `dry_run` ticked. Check the outcome, the counts, `error_summary`,
    `error_class` and `error_gmail_id`; the last three are empty when all is well.
  - Admin → Mailbox access logs: a `backfill` row with `dry_run` ticked, showing `api_calls` and `messages_read`.
  - Admin → Capture mailboxes: `last_error` is empty. A dry run never changes the mailbox's health fields or its
    starting point.
  - Mail messages: no row.
- **Why not an incremental dry run:** a dry run saves nothing, including the starting point. On a new mailbox, an
  incremental dry run therefore counts nothing, and so does every one after it.

### Step 3: store the test mail

```
python manage.py gmail_sync --backfill --since <yesterday> --max-messages 20 --mailbox test-mailbox@example.com
echo "exit code $?"
```

- **Expect:** outcome `ok`, `stored=` matching step 2's `matched=`, and exit code 0.
- **Look at:**
  - **Capture runs:** the outcome, and `stored`, `matched`, `unmatched`, `failed` and `gone`.
  - **Mailbox access logs:** the read is on record.
  - **Capture mailboxes:** `history id` is now set (this run saved the starting point), `last_error` is empty and
    `consecutive_errors` is 0.
  - **Mail messages and Unmatched senders:** only the test mail.
  - **Capture failures:** empty.

### Step 4: one incremental run

Send one more test message to the test mailbox, then run:

```
python manage.py gmail_sync --incremental --mailbox test-mailbox@example.com
echo "exit code $?"
```

- **Expect:** `stored=1` and exit code 0. This reads only what arrived after step 3.

**Stop after step 4 and report what you saw.** Leave the mailbox enabled only if further runs have a go-ahead.

A second run on the same mailbox while one is still running exits 7 (`busy`). Wait for the first to finish.

## 2. How to remove the test data

Mail is removed only through a confirmed rule or a Gmail label. Each removal is recorded in Capture purges, and the
CRM gets the "message purged" signal.

Choose one route.

### Route A: label (simplest; needs one more run)

1. In the test mailbox, apply the Gmail label `CRM private` to the test messages.
2. With the mailbox still enabled, run:

   ```
   python manage.py gmail_sync --incremental --mailbox test-mailbox@example.com
   ```

   The labelled copies are removed.
3. Then untick `enabled` on the test mailbox.

### Route B: rule (no Gmail call)

1. Untick `enabled` on the test mailbox, so nothing new arrives.
2. In the admin, add one **address rule** per test sender, with kind `address`, the sender's full address and
   action `skip`. Use scope `mailbox` with the test mailbox to limit it.

   A **domain** rule fits only when the senders write from a company domain. A domain rule on a public mail
   provider (a personal webmail account) or on one of our own domains is refused. Mail from our own domains is never
   stored anyway.
3. Saving opens the preview, which shows how many messages, conversations and queue rows would go. Check the
   numbers, then press **Confirm purge**.

   If the rule was edited after the preview, the confirmation is refused: "the rule changed since the preview:
   preview again". Open the preview again.

### What stays

Run rows and access-log rows hold no mail content. They are the record that the mailbox was read, and they expire
after `CAPTURE_RUN_RETENTION_DAYS` and `CAPTURE_ACCESS_LOG_RETENTION_DAYS`.

### Label rules

A label rule (for example one on a label `Clients`) purges only the stored copies its preview showed. Copies
labelled after the preview are reported ("2 more messages carry this label since the preview: preview again to
purge them") and wait for a new preview and confirmation.

A preview can be confirmed for 60 minutes. New mail carrying the label is never captured from the moment the rule
is saved. The built-in `CRM private` label always acts at once.

## 3. Outcomes and exit codes

`gmail_sync` exits with one of these codes. When several mailboxes run (`--all-mailboxes`), the most severe wins, in
the order 2, 3, 8, 1, 6, 4, 7, 5, 0. The same list is in `python manage.py gmail_sync --help`.

| Exit | Meaning | Run outcomes | What to do |
|---|---|---|---|
| 0 | ok | `ok`; `partial` (stopped at `--max-messages` or the budget; the next run continues); `resync_needed` (the history cursor expired; the next run resyncs a window by itself); also `capture disabled` while `GOOGLE_CAPTURE_ENABLED` is off | nothing |
| 1 | run error | `error` (a message or code error), or the client could not be made | read `error_summary`, `error_class` and `error_gmail_id` on the run |
| 2 | bad arguments | none, nothing ran: a `--mailbox` that is unknown, not enabled or on `GOOGLE_CAPTURE_NEVER_MAILBOXES`, neither `--mailbox` nor `--all-mailboxes`, or a refused `--skip-once` | correct the command |
| 3 | auth error | `auth_error`: authentication or permission refused | follow the hint (delegation entry, scope, service account id, Token Creator, API enabled); the next good token clears it |
| 4 | temporary problem | `rate_limited`; `unavailable` (Gmail failing on everything, or the token endpoint unreachable); `deferred` (backing off after one of these; no Gmail call) | wait; a later run continues; `--check` shows the backoff time |
| 5 | ok with failures | `ok_with_failures`: some messages failed or were parked | read Capture failures; see section 4 |
| 6 | needs attention | `needs_attention`: the mailbox stopped (section 4) | see section 4 |
| 7 | busy | `busy`: another run holds the mailbox's lease | wait for it to finish |
| 8 | not configured | none: capture is on but cannot run (`CAPTURE_INTERNAL_DOMAINS` unsound, no mailbox enabled, credentials mode off or invalid) | fix the setting named |

`--check` uses the same codes. It reports 3 for a refused token, 4 for an unreachable one, and 6 for a mailbox that
needs attention, even when the profile read itself worked.

## 4. Failures, parked messages and "needs attention"

### One message Gmail refuses

- A message that is gone (404 or 410) is counted as `gone` and skipped.
- A 400, or a 5xx repeated on that one message, becomes that message's Capture failure, and the cursor moves on.
- A failed message is retried on the next runs. After 3 attempts it is **parked**.

### Parked messages

Parked messages are tried again when the code version changes:

- on Render, `RENDER_GIT_COMMIT` changes with every deploy;
- elsewhere, the version is `ENGINE_VERSION` plus a hash of this app's migration file names.

So a fix deployed on Render brings parked messages back by itself, and each deploy also gives genuinely bad
messages 3 more tries, which is harmless. On a host without `RENDER_GIT_COMMIT`, a code fix that adds no migration
does not change the version. Then either:

- run `python manage.py mail_capture_unpark --mailbox test-mailbox@example.com`, or use the Unpark action on
  Capture failures; or
- raise `ENGINE_VERSION` in `mail_capture/sync.py`.

### Temporary failures

These are temporary:

- rate limits;
- Gmail failing on every call;
- the token endpoint unreachable.

They end the run `rate_limited` or `unavailable`. The mailbox then **backs off**: runs before the time shown end
`deferred`, without reading Gmail. The wait starts at 1 minute and doubles up to 60, or follows Gmail's
`Retry-After`.

Temporary failures alone mark the mailbox "needs attention" only after `CAPTURE_TRANSIENT_ATTENTION_HOURS` (24 by
default) of nothing else. The reason then reads "only temporary failures for 24 hours (last: ...)".

### Refused authentication

A refused token or a permission error shows at once: `auth_problem` on the mailbox, and in `--check`. It never stops
the mailbox, and the next good token clears it. No `--clear-attention` is needed after fixing the setup.

### Needs attention

A run that fails on one message, or on a code error, ends `error` and records the Gmail id and the exception class.
After `CAPTURE_ATTENTION_AFTER_ERRORS` such runs in a row (3 by default), the mailbox is marked **needs attention**:

- it is logged once at ERROR;
- it shows in the Capture mailboxes list, which has a filter for it;
- `--check` reports it.

From then on, runs of that mailbox stop without reading Gmail until a person acts:

- **Skip the message named in `attention_reason`.** This **skips the message for good**: it is never captured.
  Who, when and why are recorded. Use it only for the id that `attention_reason`, or the last failed run, names. Any
  other id is refused unless `--force` is added, and the force is recorded on the skip.

  ```
  python manage.py gmail_sync --skip-once <gmail id> --mailbox test-mailbox@example.com --by "<your name>" --reason "<why>"
  ```

- **Fixed the cause:** use the "Clear needs attention" action in the admin, or run the command below. It also ends
  any backoff.

  ```
  python manage.py gmail_sync --clear-attention --mailbox test-mailbox@example.com --by "<your name>" --reason "<why>"
  ```

- **Deploy a fix:** a new code version clears the flag by itself on the next run.

No alert e-mail is sent. Watch the ERROR log line or the exit code.

## 5. Pacing and budgets

Before every call, the client waits for enough quota in two token buckets:

- **per mailbox:** Gmail's 6,000 units per user per minute;
- **per process:** Gmail's 1,200,000 units per project per minute.

A backfill therefore runs slower but stays under the limit instead of stopping `rate_limited`. A batch of 50
messages costs 1,000 units, so a mailbox reads at most about 300 messages a minute.

A second run on the same mailbox exits 7 (`busy`), because the mailbox's lease allows one run at a time. So the
per-mailbox limit cannot be doubled by starting two processes.

A real 429 still backs off. It honours Gmail's `Retry-After` when sent; otherwise it waits 15, 30 and then
60 seconds.

`--max-messages` and the internal quota budget are never overshot: the last batch asks only for as many messages as
remain.

## 6. Settings

Only names appear here. The values live in the capture service's environment on Render.

| Setting | Where | What |
|---|---|---|
| `GOOGLE_CAPTURE_ENABLED` | environment | master switch, default off; set it last |
| `CAPTURE_INTERNAL_DOMAINS` | environment | our own mail domains, comma-separated; capture refuses to run while empty or unsound |
| `CAPTURE_INTERNAL_ADDRESSES` | environment | single internal addresses on other domains |
| `CAPTURE_EXTRA_FREEMAIL_DOMAINS` | environment | more public mail providers |
| `GOOGLE_CAPTURE_CREDENTIALS_MODE` | environment | `off` (default), `keyless` or `key_file` |
| `GOOGLE_CAPTURE_SERVICE_ACCOUNT` | environment | the service account's address (keyless mode) |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | environment, written by Render's federation set-up | keyless mode only |
| `GOOGLE_CAPTURE_KEY_FILE` | environment: a path to a Render secret file, never the key itself | key-file mode only |
| `GOOGLE_CAPTURE_SCOPE` | environment | `metadata` (default, headers only) or `readonly` (bodies) |
| `GOOGLE_CAPTURE_NEVER_MAILBOXES` | environment | mailboxes never read, whatever the table says; set it first |
| `CAPTURE_ATTENTION_AFTER_ERRORS` | environment | message or code errors in a row before "needs attention" (default 3) |
| `CAPTURE_TRANSIENT_ATTENTION_HOURS` | environment | hours of only temporary failures before "needs attention" (default 24) |
| `CAPTURE_GMAIL_USER_UNITS_PER_MINUTE` | environment | pacing per mailbox (default 6000; lower only) |
| `CAPTURE_GMAIL_PROJECT_UNITS_PER_MINUTE` | environment | pacing per project (default 1200000; lower only) |
| `CAPTURE_RUN_RETENTION_DAYS` | environment | how long run rows are kept (default 90) |
| `CAPTURE_ACCESS_LOG_RETENTION_DAYS` | environment | how long access-log rows are kept (default 365) |
| `RENDER_GIT_COMMIT` | set by Render | the code version for parked messages and "needs attention" |
| `LOGGING` (`google` and `googleapiclient` pinned to INFO) | `bmasia_crm/settings.py` | keeps the Google libraries' DEBUG logging (request and response bodies) off, whatever the root level |
| Capture mailboxes, rules and company domains | the database, through the admin (superusers only) | which mailboxes run, never-log rules, company domains |

Never put a key, a token or a key path in a log, a ticket or a chat.

## 7. Before any real person's mailbox

The test mailbox is the only mailbox until all of these are done:

1. **Never-list.** `GOOGLE_CAPTURE_NEVER_MAILBOXES` lists every mailbox that must never be read. It is checked again
   before every credential is made.
2. **Staff notice.** The PDPA notice to staff has gone out. It says:
   - what is captured (headers only, by default);
   - why;
   - who can see it;
   - how to keep a thread out (the `CRM private` label);
   - how long it is kept.
3. **Domain seeding, dry run first:**

   ```
   python manage.py mail_capture_seed_domains
   ```

   Review the proposals. A domain shared by two companies is skipped and reported, and freemail and our own domains
   are never proposed. Only then run it with `--apply`. Without company domains, many colleagues of known contacts
   end up ambiguous or unmatched.
4. **Go-ahead.** A go-ahead to enable that one mailbox. Then start again from section 1: `--check`, the dry run,
   one stored run, always with `--mailbox`.
