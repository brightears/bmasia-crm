#!/usr/bin/env python3
"""bmasia-quote-receipt: ask the protected quote attestor for a signed send receipt.

Usage (as Lyra's `bmasia` or Theo's `theo_ai` account, after the quote email was sent):
  bmasia-quote-receipt --quote-id UUID --quote-number HK-QT26154 \
      --expected-version 2026-09-25T08:14:37.123456Z --gmail-message-id <Gmail id>

Prints {"ok": true, "receipt": {...}} or {"ok": false, "error": "<reason>"}; exit 0 only on ok.
Pass the receipt to Cira as authorization_context
{"kind": "signed_quote_send_bookkeeping", "receipt": <receipt>} with patch
{"status": "Sent", "sent_date": <from the receipt>} and expected_values
{"status": "Draft", "sent_date": null}. The sending mailbox is fixed by your Unix account.
"""
import argparse
import json
import socket
import sys

SOCKET = "/run/bmasia-quote-send-receipt/attestor.sock"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quote-id", required=True)
    parser.add_argument("--quote-number", required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--gmail-message-id", required=True)
    args = parser.parse_args()
    request = {"quote_id": args.quote_id, "quote_number": args.quote_number,
               "expected_version": args.expected_version, "gmail_message_id": args.gmail_message_id}
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
        conn.settimeout(150)
        conn.connect(SOCKET)
        conn.sendall(json.dumps(request, separators=(",", ":")).encode("ascii") + b"\n")
        data = b""
        while not data.endswith(b"\n") and len(data) < 65536:
            chunk = conn.recv(8192)
            if not chunk:
                break
            data += chunk
    result = json.loads(data or b'{"ok": false, "error": "no_response"}')
    print(json.dumps(result))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    sys.exit(main())
