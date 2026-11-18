# Mail capture: operator runbook

This runbook covers the first supervised run, the outcomes and exit codes, how to stop, how to remove test data,
and the settings. Nothing in this app runs by itself: there is no cron. Every command below is started by a person,
and on production each one needs a go-ahead first.

The examples use `test-mailbox@example.com`. Replace it with the address of the test mailbox that was made for this
purpose. Never use a real person's mailbox for the first runs.

## 0. Before the first run

- **Google side (super admin):**
  - the service account;
  - domain-wide delegation for exactly `https://www.googleapis.com/auth/gmail.metadata`;
  - for keyless mode, the workload identity pool and provider, and Service Account Token Creator for the federated
    principal on the service account;
  - one test mailbox, made for this purpose, holding only test mail.
- **Capture service settings:** set them as described in section 7. Set `GOOGLE_CAPTURE_NEVER_MAILBOXES` before
  anything else is enabled.
- **The mailbox row:** in the admin, under Mail capture → Capture mailboxes, add `test-mailbox@example.com` with
  `enabled` ticked and `body_mode` left at headers only.
- **The self-check** (synthetic fixtures, rolled back, no Gmail call):

  ```
  python manage.py mail_capture_selfcheck
  ```

  It must report the switch state you expect and a passing pipeline.

## 1. The first supervised run, in this order

Run each step only after the one before it looked right.

### Step 1: `--check` (1 quota unit, stores nothing but its access-log row)

```
python manage.py gmail_sync --check --mailbox test-mailbox@example.com
echo "exit code $?"
```

- **Expect:** `test-mailbox@example.com: messages N, history id H` and exit code 0. This proves the delegation, the
  credential path (keyless signBlob or the key file) and the scope.
- **Look at:**
  - Admin → Mailbox access logs: one row, purpose `check`, `api_calls` 1, `finished_at` set.
  - The exit code (section 4).
- **If it says `auth_error <code>: <hint>`:** the hint names the setup step to fix, for example the delegation
  entry, the scope, the service account id, the Token Creator role, or the API not being enabled. Fix that on the
  Google side and repeat step 1. Do not go on.

### Step 2: `--incremental --dry-run` (reads and counts; stores no mail)

```
python manage.py gmail_sync --incremental --dry-run --mailbox test-mailbox@example.com
echo "exit code $?"
```

- The first incremental run on a new mailbox reads only the profile: it sets the starting point. Send one or two
  test messages to the test mailbox, then run step 2 again, so there is something to count.
- **Expect:** `test-mailbox@example.com: ok ...counts...` and exit code 0.
- **Look at:**
  - Admin → Capture runs: the newest row, with `dry_run` ticked, the outcome, the counts, `error_summary`,
    `error_class` and `error_gmail_id` (empty when all is well).
  - Admin → Mailbox access logs: a row with `dry_run` ticked, `api_calls` and `messages_read`.
  - Admin → Capture mailboxes: `last_error` must be empty. A dry run never changes the mailbox's health fields.
  - No row in Mail messages.

### Step 3: one stored incremental run

```
python manage.py gmail_sync --incremental --mailbox test-mailbox@example.com --max-messages 20
echo "exit code $?"
```

- **Expect:** outcome `ok` (or `partial` if `--max-messages` was reached) and exit code 0.
- **Look at:**
  - **Capture runs:** outcome, `stored`, `matched`, `unmatched`, `failed`, `gone`.
  - **Mailbox access logs:** the read is on record.
  - **Capture mailboxes:** `history id` has moved, `last_error` is empty and `consecutive_errors` is 0.
  - **Mail messages and Unmatched senders:** only the test mail.
  - **Capture failures:** should be empty. Each row has a Gmail id and an error code, never mail content.

Stop after step 3 and report what you saw. Leave the mailbox enabled only if the next runs have a go-ahead.

## 2. How to stop

- **Everything at once:** set `GOOGLE_CAPTURE_ENABLED` to false on the capture service. From the next command on,
  every form prints `capture disabled: GOOGLE_CAPTURE_ENABLED is off` and exits 0, before any credential or client
  is made. A run already in progress is not interrupted by the switch; stop it with Ctrl-C if it must end now.
- **One mailbox:** untick `enabled` on its row in the admin (the change is written to the access log). Or add the
  address to `GOOGLE_CAPTURE_NEVER_MAILBOXES`, which wins over the table.
- **No credential at all:** set `GOOGLE_CAPTURE_CREDENTIALS_MODE` to `off`.
- **Ctrl-C during a run:** this is safe. The cursor only moves together with a finished page, the lease is
  released, and the run row stays `running`.

## 3. How to remove the test data

Mail is removed only through a confirmed rule or a Gmail label. Each of these is recorded in Capture purges, and
the CRM gets the "message purged" signal.

1. **Disable first:** untick `enabled` on the test mailbox, so nothing new arrives.
2. **Domain rule:** in the admin, add a Capture rule:
   - kind `domain` and the value of the test senders' domain;
   - action `skip`;
   - scope `mailbox` and the test mailbox.

   Saving opens the preview, which shows how many messages, conversations and queue rows would go. Check the numbers,
   then press **Confirm purge**. If the rule was edited after the preview, the confirmation is refused ("the rule
   changed since the preview: preview again"); open the preview again.
3. **Label instead:** in the test mailbox, apply the Gmail label `CRM private` to the test messages. The next run
   removes them. This needs the mailbox to be enabled for one more run.
4. **Records that stay:** run rows and access-log rows hold no mail content. They are the record that the mailbox
   was read, and they expire after `CAPTURE_RUN_RETENTION_DAYS` and `CAPTURE_ACCESS_LOG_RETENTION_DAYS`.

## 4. Outcomes and exit codes

`gmail_sync` exits with one of these codes. When several mailboxes run, the most severe wins, in the order
2, 3, 8, 1, 6, 4, 7, 5, 0. The same list is in `python manage.py gmail_sync --help`.

| Exit | Meaning | Run outcomes | What to do |
|---|---|---|---|
| 0 | ok | `ok`; `partial` (stopped at `--max-messages` or the budget; the next run continues); `resync_needed` (the history cursor expired; the next run resyncs a window by itself); also `capture disabled` while `GOOGLE_CAPTURE_ENABLED` is off | nothing |
| 1 | run error | `error`, or the client could not be made | read `error_summary`, `error_class` and `error_gmail_id` on the run |
| 2 | bad arguments | none (nothing ran); includes a `--mailbox` that is unknown, not enabled, or on `GOOGLE_CAPTURE_NEVER_MAILBOXES` | correct the command |
| 3 | auth error | `auth_error`: authentication or permission refused; never retried | follow the hint (delegation entry, scope, service account id, Token Creator, API enabled) |
| 4 | rate limited | `rate_limited`: Gmail kept answering 429 after backoff; finished work is kept | wait; the next run continues |
| 5 | ok with failures | `ok_with_failures`: some messages failed or were parked | read Capture failures; see section 5 |
| 6 | needs attention | `needs_attention`: the mailbox stopped after repeated failed runs | see section 5 |
| 7 | busy | `busy`: another run holds the mailbox's lease | wait, or check nothing else is running |
| 8 | not configured | none: capture is on but cannot run (`CAPTURE_INTERNAL_DOMAINS` unsound, no mailbox enabled, credentials mode off or invalid) | fix the setting named |

`--check` uses the same codes. It reports 3 for an auth error and 6 for a mailbox that needs attention, even when
the profile read itself worked.

## 5. Failures, parked messages and "needs attention"

### One message Gmail refuses

A message that is gone (404 or 410) is counted as `gone` and skipped. A 400, or a 5xx repeated on that one message,
becomes that message's Capture failure, and the cursor moves on.

A failed message is retried on the next runs. After 3 attempts it is **parked**.

### Parked messages

Parked messages are tried again when the code version changes:

- on Render, `RENDER_GIT_COMMIT` changes with every deploy;
- elsewhere, the version is `ENGINE_VERSION` plus a hash of this app's migration files.

So a fix deployed on Render brings parked messages back by itself, and each deploy also gives genuinely bad
messages 3 more tries, which is harmless. On a host without `RENDER_GIT_COMMIT`, a code fix that adds no migration
does not change the version. In that case:

- run `python manage.py mail_capture_unpark --mailbox test-mailbox@example.com`, or use the Unpark action on
  Capture failures; or
- raise `ENGINE_VERSION` in `mail_capture/sync.py`.

### Needs attention

A run that fails on one message ends `error`. It records that message's Gmail id and the exception class on the run
row. After `CAPTURE_ATTENTION_AFTER_ERRORS` failed runs in a row (3 by default), the mailbox is marked **needs
attention**:

- it is logged once at ERROR;
- it shows in the Capture mailboxes list, with its filter;
- `gmail_sync --check` reports it.

Runs of that mailbox then stop, without reading Gmail, until a person acts. There are three ways to act:

- **Skip that one message once.** The skip is recorded with who, when and why:

  ```
  python manage.py gmail_sync --skip-once <gmail id> --mailbox test-mailbox@example.com --by "<your name>" --reason "<why>"
  ```

- **Fixed the cause:** use the "Clear needs attention" action in the admin, or:

  ```
  python manage.py gmail_sync --clear-attention --mailbox test-mailbox@example.com --by "<your name>" --reason "<why>"
  ```

- **Deploy a fix:** a new code version clears the flag by itself on the next run.

No alert e-mail is sent. Watch the ERROR log line or the exit code.

## 6. Pacing and budgets

Before every call, the client waits for enough quota in two token buckets:

- per mailbox, for Gmail's 6,000 units per user per minute;
- per process, for the 1,200,000 units per project per minute.

A backfill therefore runs slower but stays under the limit instead of stopping `rate_limited`. A batch of 50
messages costs 1,000 units, so a mailbox reads at most about 300 messages a minute.

A real 429 still backs off: it honours Gmail's `Retry-After` when sent, otherwise it waits 15, 30 and then 60
seconds.

`--max-messages` and the internal quota budget are never overshot: the last batch asks only for as many messages as
remain.

## 7. Settings (names only; values live in the capture service's environment on Render)

| Setting | Where | What |
|---|---|---|
| `GOOGLE_CAPTURE_ENABLED` | environment | master switch, default off |
| `CAPTURE_INTERNAL_DOMAINS` | environment | our own mail domains, comma-separated; capture refuses to run while empty or unsound |
| `CAPTURE_INTERNAL_ADDRESSES` | environment | single internal addresses on other domains |
| `CAPTURE_EXTRA_FREEMAIL_DOMAINS` | environment | more public mail providers |
| `GOOGLE_CAPTURE_CREDENTIALS_MODE` | environment | `off` (default), `keyless` or `key_file` |
| `GOOGLE_CAPTURE_SERVICE_ACCOUNT` | environment | the service account's address (keyless mode) |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | environment, written by Render's federation set-up | keyless mode only |
| `GOOGLE_CAPTURE_KEY_FILE` | environment: a path to a Render secret file, never the key itself | key-file mode only |
| `GOOGLE_CAPTURE_SCOPE` | environment | `metadata` (default, headers only) or `readonly` (bodies) |
| `GOOGLE_CAPTURE_NEVER_MAILBOXES` | environment | mailboxes that are never read, whatever the table says |
| `CAPTURE_ATTENTION_AFTER_ERRORS` | environment | failed runs in a row before "needs attention" (default 3) |
| `CAPTURE_GMAIL_USER_UNITS_PER_MINUTE` | environment | pacing per mailbox (default 6000; lower only) |
| `CAPTURE_GMAIL_PROJECT_UNITS_PER_MINUTE` | environment | pacing per project (default 1200000; lower only) |
| `CAPTURE_RUN_RETENTION_DAYS` | environment | how long run rows are kept (default 90) |
| `CAPTURE_ACCESS_LOG_RETENTION_DAYS` | environment | how long access-log rows are kept (default 365) |
| `RENDER_GIT_COMMIT` | set by Render | the code version for parked messages and "needs attention" |
| `LOGGING` (`google`, `googleapiclient` pinned to INFO) | `bmasia_crm/settings.py` | keeps the Google libraries' DEBUG logging (request and response bodies) off whatever the root level |
| Capture mailboxes, rules and company domains | the database, through the admin (superusers only) | which mailboxes run, never-log rules, company domains |

Never put a key, a token or a key path in a log, a ticket or a chat.

## 8. Before any real person's mailbox

The test mailbox is the only mailbox until all of these are done:

1. **Never-list:** `GOOGLE_CAPTURE_NEVER_MAILBOXES` lists every mailbox that must never be read, for example the
   owner's, HR's and finance's. It is checked again before every credential is made.
2. **Staff notice:** the PDPA notice to staff has gone out, saying what is captured (headers only by default), why,
   who can see it, how to keep a thread out (the `CRM private` label), and how long it is kept.
3. **Domain seeding, dry run first:**

   ```
   python manage.py mail_capture_seed_domains
   ```

   Review the proposals: a domain shared by two companies is skipped and reported, and freemail and our own domains
   are never proposed. Only then run it with `--apply`. Without company domains, many colleagues of known contacts
   end up as ambiguous or unmatched.
4. **Go-ahead:** a go-ahead to enable that one mailbox, starting again from section 1 (`--check`, then a dry run,
   then one stored run).
