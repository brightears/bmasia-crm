# Quote send attestor (Part B)

Root-owned service on the core VPS that signs **quote-send receipts** for the CRM's guarded
quote Draft→Sent bookkeeping (`crm_app/quote_send_receipts.py`). Norbert, 2026-09-25: same
safeguards as contracts; the email in the sender's own Sent folder is the proof.

| Item | Location |
|---|---|
| Service | `bmasia-quote-send-receipt.service` (User=root) |
| Code | `/usr/local/lib/bmasia/quote-send-receipts/attestor.py` (root 0755) |
| Keys | `/etc/bmasia/quote-send-receipts/private.pem` (root 0400), `public.der` (root 0644) |
| Socket | `/run/bmasia-quote-send-receipt/attestor.sock` (0666; authorization = kernel peer UID) |
| Client | `/usr/local/bin/bmasia-quote-receipt` |

Callers: Unix `bmasia` (Lyra) → only `norbert@bmasiamusic.com`; `theo_ai` (Theo) → only
`nikki.h@bmasiamusic.com`. Every other account gets `peer_not_allowed`. Note: `bmasia` has sudo,
so Lyra's account is inside the host-administrator trust boundary (same limitation as the
agent report channel).

Checks before signing: SENT label (not a draft), From = the mailbox, ≥1 recipient outside
bmasiamusic.com, an attached PDF whose text (pdftotext) contains the quote number, sent within
90 days. Receipt valid 10 minutes; the CRM binds it to record id, quote number, version,
Draft/null before-values, the patch, Gmail provider date = sent_date (Bangkok) and
mailbox↔requester; single use via `QuoteSendReceiptUse`.

Use (after the quote email is sent):

```bash
bmasia-quote-receipt --quote-id UUID --quote-number HK-QT26154 \
  --expected-version '<quote updated_at from a fresh CRM read>' --gmail-message-id <Gmail id>
```

Then send Cira an `update` of the quote with patch `{"status": "Sent", "sent_date": <receipt patch
sent_date>}`, `expected_values` `{"status": "Draft", "sent_date": null}`, the same
`expected_version`, and `authorization_context` `{"kind": "signed_quote_send_bookkeeping",
"receipt": <receipt>}`.

Install / rollback: install the three files as above, `systemctl daemon-reload && systemctl enable
--now bmasia-quote-send-receipt`. Rollback: `systemctl disable --now bmasia-quote-send-receipt`
(the CRM then simply refuses quote Sent bookkeeping). Key rotation = new key pair + reviewed CRM
commit pinning the new `public.der`.

Tests: `pytest -p no:django -c /dev/null --rootdir deploy/quote-send-attestor deploy/quote-send-attestor/test_attestor.py`
(includes a cross-check that the CRM verifier accepts a receipt this attestor signs).
