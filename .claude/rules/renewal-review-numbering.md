# Numbered renewal PDF review

Cira's existing `generate_contract_pdf` MCP tool accepts the opt-in arguments
`reserve_renewal_number=true` and `expected_version=<current updated_at>` for an
existing linked renewal Draft. Default PDF generation remains unchanged.

The opt-in path locks the contract, checks its version and predecessor company,
reserves a final number with the same collision-safe sequence helper used by the
dedicated Rene preparation path, and renders before committing. Only the final
number and `updated_at` change. Status remains Draft, `sent_date` remains null,
the existing `is_active` value is preserved, and the predecessor is untouched.
A rendering error rolls back the reservation. Already numbered Drafts reuse
their number; stale versions require a fresh read. No migration is needed.

Theo requests this through Cira's existing structured relay. Cira must inspect
and publish the resulting numbered PDF for Nikki's review before customer
sending. Do not mark a contract Sent to manufacture a number or regenerate a
different PDF after Nikki approves the frozen attachment. A confirmed customer
send can advance status later; the reserved number remains unchanged.

The dedicated Rene transport, credentials, receipts, and authority remain
unchanged. This does not create an email, invoice, or activation operation.
