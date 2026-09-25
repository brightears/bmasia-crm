"""
MCP Server tools for BMAsia CRM.

Exposes core CRM ViewSets as MCP tools via django-mcp-server.
Endpoint: /mcp/ with Token authentication.
"""
import base64
import json
import logging
import re
from datetime import date, datetime, timezone

from django.db import IntegrityError, transaction
from django.db.models import Q

from mcp_server import mcp_server
from mcp_server.djangomcp import MCPToolset
from mcp_server.query_tool import ModelQueryToolset

from crm_app.models import (
    Company, Contact, Contract, Invoice, Quote, Opportunity, AuditLog,
    Task, Zone, ContractTemplate, ContractLineItem, InvoiceLineItem, QuoteLineItem,
    ContractServiceLocation, ClientTechDetail, Device, Ticket, KBArticle,
    ContractSendReceiptUse, QuoteSendReceiptUse,
)
from crm_app.contract_send_receipts import (
    ReceiptVerificationError, verify_signed_contract_send_context,
)
from crm_app.quote_send_receipts import (
    ReceiptVerificationError as QuoteReceiptVerificationError,
    verify_signed_quote_send_context,
)
from crm_app.rene_auth import is_exact_rene_phase2_mcp_request
from crm_app.services import agent_gate as _agent_gate
from crm_app.rene_mcp_server import rene_phase2_mcp_server
from crm_app.views import ContractViewSet, QuoteViewSet, InvoiceViewSet  # Only for PDF tools

logger = logging.getLogger(__name__)

# ============================================================
# Server instructions
# ============================================================

mcp_server.append_instructions("""
# BMAsia CRM - MCP Server

You are interacting with the BMAsia CRM system for managing music services clients
across Thailand and Hong Kong.

## Available Operations

### Query Tools (read)
Use `query_data_collections` to search and filter any collection using MongoDB-style
aggregation pipelines. Available collections: company, contact, contract, invoice,
quote, opportunity, task, zone, clienttechdetail, device, ticket, kbarticle,
quotelineitem, contractlineitem, servicelocation, invoicelineitem,
contracttemplate.

### CRUD Tools (write)
Use these 3 generic tools for all write operations:
- `create_record(collection, data)` — create a new record (data is a JSON string)
- `update_record(collection, id, data)` — partial update (only include changed fields)
- `delete_record(collection, id)` — delete a record

Supported collections: company, contact, contract, invoice, quote, opportunity,
task, zone, clienttechdetail, device, ticket, kbarticle, quotelineitem,
contractlineitem, servicelocation, invoicelineitem, contracttemplate.
Contract templates may be queried, created, and updated through these tools;
generic template deletion is intentionally blocked.

### PDF Tools
Each returns a JSON string with `filename`, `size`, and `content_b64` (base64-
encoded PDF bytes). Parse with `json.loads`, then `base64.b64decode(content_b64)`
to recover the raw PDF. On failure returns `{"error": "..."}`.
- `generate_contract_pdf(id, reserve_renewal_number=false, expected_version="")` — generate
  a contract PDF. Cira may opt in to reserve a linked renewal Draft's final number
  before Nikki reviews it, supplying current updated_at as expected_version.
  This preserves Draft status and does not mark or send the contract as delivered.
- `generate_proforma_pdf(id)` — generate PROFORMA INVOICE PDF from a contract (advance-payment
  request for the renewal pack; marked "not a tax invoice"; creates no Invoice/AR/tax record)
- `generate_quote_pdf(id)` — generate quote PDF
- `generate_invoice_pdf(id)` — generate invoice PDF
- `get_commercial_document_context(collection, id)` — read current issuer,
  currency, document fields and writable field names before tailoring a draft.

## Key Concepts
- **billing_entity**: 'BMAsia (Thailand) Co., Ltd.' or 'BMAsia Limited'. On
  quote/contract/invoice this is an optional document-only issuer override;
  blank uses company.billing_entity. Currency and customer country are independent
  choices: a Hong Kong customer may receive a Thailand-issued USD document.
  Set the document override for a one-off exception; do not change the Company
  just to tailor one document. Read effective_billing_entity with
  get_commercial_document_context before and after an authorized change.
- **Tailoring**: use quote line items, payment_schedule and terms_conditions;
  contract preamble_custom, payment_custom, activation_custom, custom_terms,
  payment_schedule, service items/locations and signatories. Saved templates are
  reusable starting points, not a mandatory catalogue of permitted commercial deals.
  Corporate full-template edits must use that template's explicit editable slots;
  if a slot is missing, follow the PDF error's clarification instead of silently
  dropping a clause or appending a differently styled PDF. Never put customer
  terms in notes (internal only). Preserve approved legal text and request a
  clarification for missing issuer, pricing, tax or contractual authority.
- **Contract status**: Draft → Sent → Active → Renewed/Expired/Cancelled
- **Invoice status**: Draft → Sent → Paid/Overdue/Void
- **Quote status**: Draft → Sent → Accepted/Rejected/Expired
- **Service locations** on contracts are separate from line items — they control
  what appears in the PDF "Locations for Provision of Services" table.
  A normal contract update is an ID-aware partial upsert and preserves omitted
  rows. To replace the complete list atomically, call `update_record` once for
  the contract with `replace_service_locations: true`, the complete intended
  `service_locations` array, and any matching pricing fields such as `value`.
  Existing rows omitted from that complete list are deleted only in this explicit
  mode, and the whole update rolls back if pricing validation fails.
- Contract numbers are auto-generated (read-only).
""")


class RenePhase2MCPToolset(MCPToolset):
    """Dedicated Cira adapter for the frozen Rene renewal contract."""

    mcp_server = rene_phase2_mcp_server

    def rene_phase2_request(self, request_json: str) -> str:
        """Execute or look up one exact frozen Rene request.

        ``request_json`` must be one duplicate-free UTF-8 JSON object no larger
        than 15 MiB. This tool never accepts a collection name or CRUD verb.
        """

        from crm_app.services.rene_phase2_transport import (
            CiraJsonParseError,
            parse_cira_json_bytes,
        )
        from crm_app.services.rene_phase2 import (
            LOOKUP_SCHEMA,
            RenePhase2BoundError,
            RenePhase2Error,
            execute_rene_request,
            lookup_rene_receipt,
            materialize_rene_wire_response,
            safe_error,
            unbound_error,
        )
        from crm_app.services.rene_phase2_common import canonical_json

        # Phase 1 Stage A: record every call, including refused ones (observe only).
        # The frozen Rene boundary, its journal and receipts are unchanged; the
        # payload itself is not parsed here.
        _agent_gate.observe(tool='rene_phase2_request', verb='rene_request', collection='contract',
                            user=getattr(self.request, 'user', None))

        if not is_exact_rene_phase2_mcp_request(self.request):
            return canonical_json(
                unbound_error(
                    'FORBIDDEN',
                    'the exact configured Cira MCP principal is required',
                    crm_mcp_invoked=True,
                )
            )
        if not isinstance(request_json, str):
            return canonical_json(
                unbound_error(
                    'INVALID_JSON',
                    'Cira request must be one UTF-8 JSON string',
                    crm_mcp_invoked=True,
                )
            )
        result_ready = False
        try:
            raw = request_json.encode('utf-8')
            request = parse_cira_json_bytes(raw)
            if request.get('schema') == LOOKUP_SCHEMA:
                result = lookup_rene_receipt(request)
            else:
                result = execute_rene_request(request, crm_mcp_invoked=True)
            result_ready = True
            return canonical_json(materialize_rene_wire_response(result))
        except CiraJsonParseError as exc:
            return canonical_json(
                unbound_error(
                    exc.code,
                    str(exc),
                    crm_mcp_invoked=True,
                )
            )
        except UnicodeError:
            return canonical_json(
                unbound_error(
                    'INVALID_JSON',
                    'Cira request must be one UTF-8 JSON string',
                    crm_mcp_invoked=True,
                )
            )
        except RenePhase2BoundError as exc:
            return canonical_json(safe_error(exc))
        except RenePhase2Error:
            if result_ready:
                logger.exception('Rene Phase 2 portable artifact delivery failed')
                return canonical_json(
                    unbound_error(
                        'INTERNAL_ERROR',
                        'durable CRM receipt exists but its portable PDF is unavailable; '
                        'retry receipt lookup',
                        crm_mcp_invoked=True,
                    )
                )
            # Schema/hash/authority failures before durable request admission
            # have no trustworthy binding or effect proof.
            return canonical_json(
                unbound_error(
                    'INVALID_REQUEST',
                    'Cira request was rejected before durable CRM admission',
                    crm_mcp_invoked=True,
                )
            )
        except Exception:
            logger.exception('Rene Phase 2 MCP request became uncertain')
            return canonical_json(
                unbound_error(
                    'INTERNAL_ERROR',
                    'Rene CRM operation outcome is uncertain; use receipt lookup',
                    crm_mcp_invoked=True,
                )
            )

# ============================================================
# Query Toolsets (read — MongoDB-style aggregation pipeline)
# ============================================================


class CompanyQuery(ModelQueryToolset):
    model = Company
    fields = [
        'id', 'name', 'legal_entity_name', 'billing_entity', 'industry',
        'phone', 'email', 'website', 'country', 'city', 'address',
        'full_address', 'is_active', 'is_corporate_parent', 'parent_company',
        'contracted_product', 'contracted_zone_count', 'contracted_synced_at',
        'notes', 'created_at', 'updated_at',
    ]
    search_fields = ['name', 'legal_entity_name', 'email', 'city', 'country', 'notes']
    extra_instructions = ("Hotels, resorts, corporate clients. contracted_product (soundtrack/beatbreeze) + "
                          "contracted_zone_count are funnel-sourced; is_corporate_parent + parent_company give "
                          "the corporate group. NOTE: is_active is unreliable — judge active status by contracts.")


class ContactQuery(ModelQueryToolset):
    model = Contact
    fields = [
        'id', 'name', 'email', 'phone', 'company', 'contact_type',
        'is_primary', 'title', 'department', 'last_contacted', 'notes', 'created_at', 'updated_at',
    ]
    search_fields = ['name', 'email', 'phone', 'title', 'notes']
    extra_instructions = "Contacts belong to companies. contact_type: Primary, Billing, Technical, Decision Maker, Other."


class ContractQuery(ModelQueryToolset):
    model = Contract
    fields = [
        'id', 'contract_number', 'company', 'contract_type', 'service_type', 'status',
        'lifecycle_type', 'start_date', 'end_date', 'value', 'currency',
        'total_value', 'billing_entity', 'billing_frequency', 'payment_terms', 'payment_schedule', 'auto_renew',
        'renewal_period_months', 'renewed_from', 'renewal_notice_sent', 'sent_date',
        'contract_category', 'is_active', 'master_contract', 'notes',
        'preamble_template', 'preamble_custom', 'payment_template', 'payment_custom',
        'activation_template', 'activation_custom', 'custom_terms', 'custom_service_items',
        'property_name', 'show_zone_pricing_detail', 'price_per_zone',
        'customer_signatory_name', 'customer_signatory_title', 'additional_customer_signatories',
        'bmasia_signatory_name', 'bmasia_signatory_title',
        'customer_contact_name', 'customer_contact_title', 'customer_contact_email',
        'created_at', 'updated_at',
    ]
    search_fields = ['contract_number', 'notes', 'payment_terms']
    extra_instructions = (
        "Status lifecycle: Draft → Sent → Active → Renewed/Expired. Cancelled is terminal, "
        "reachable from Sent (renewal declined/abandoned before activation — never went live) "
        "or from Active (terminated after going live). "
        "service_type = product (Soundtrack / Beat Breeze). lifecycle_type: new/renewal/addon/churn. "
        "renewed_from links a renewal to the contract it replaced (renewal lineage). "
        "For a month's renewals use the renewal_book tool. $lookup with 'company' to join company details."
    )


class ContractTemplateQuery(ModelQueryToolset):
    model = ContractTemplate
    fields = [
        'id', 'name', 'template_type', 'content', 'pdf_format',
        'is_default', 'is_active', 'version', 'created_at', 'updated_at',
    ]
    search_fields = ['name', 'content', 'version']
    extra_instructions = (
        "Pre-approved contract language and rendering format. pdf_format: standard, "
        "corporate_master, or participation. Read the exact current content and "
        "updated_at before a guarded update; generic deletion is blocked."
    )


class InvoiceQuery(ModelQueryToolset):
    model = Invoice
    fields = [
        'id', 'invoice_number', 'company', 'contract', 'status',
        'invoice_date', 'due_date', 'paid_date', 'amount', 'tax_amount',
        'total_amount', 'currency', 'billing_entity', 'payment_terms', 'payment_terms_text',
        'property_name', 'service_period_start', 'service_period_end', 'notes', 'created_at',
    ]
    search_fields = ['invoice_number', 'notes']
    extra_instructions = "Status: Draft, Sent, Paid, Overdue, Void, Cancelled."


class QuoteQuery(ModelQueryToolset):
    model = Quote
    fields = [
        'id', 'quote_number', 'company', 'opportunity', 'status', 'quote_type',
        'valid_from', 'valid_until', 'subtotal', 'total_value', 'currency',
        'billing_entity', 'billing_frequency', 'contract_duration_months', 'payment_schedule',
        'terms_conditions', 'notes', 'created_at',
    ]
    search_fields = ['quote_number', 'notes']
    extra_instructions = ("Use convert_quote_to_contract to turn an accepted quote into a Draft contract "
                          "(copies terms + line items, derives service locations).")


class OpportunityQuery(ModelQueryToolset):
    model = Opportunity
    fields = [
        'id', 'name', 'company', 'contact', 'stage', 'value', 'currency',
        'probability', 'expected_close_date', 'lead_source', 'contact_method',
        'last_contact_date', 'follow_up_date', 'pain_points', 'decision_criteria',
        'notes', 'created_at', 'updated_at',
    ]
    search_fields = ['name', 'notes']
    extra_instructions = "Stages: Contacted, Quotation Sent, Contract Sent, Won, Lost."


class TaskQuery(ModelQueryToolset):
    model = Task
    fields = [
        'id', 'title', 'description', 'status', 'priority', 'due_date',
        'assigned_to', 'company', 'contact', 'created_at',
    ]
    search_fields = ['title', 'description']
    extra_instructions = "Status: pending, in_progress, completed, cancelled. Priority: low, medium, high, urgent."


class ZoneQuery(ModelQueryToolset):
    model = Zone
    fields = [
        'id', 'name', 'company', 'soundtrack_zone_id', 'soundtrack_account_id',
        'is_active', 'platform_type', 'notes', 'created_at', 'updated_at',
    ]
    search_fields = ['name', 'soundtrack_zone_id']
    extra_instructions = "Zones represent physical music playback areas in hotel properties."


class ClientTechDetailQuery(ModelQueryToolset):
    model = ClientTechDetail
    fields = [
        'id', 'company', 'zone', 'outlet_name', 'platform_type', 'syb_account_type',
        'anydesk_id', 'teamviewer_id', 'ultraviewer_id', 'other_remote_id',
        'system_type', 'soundcard_channel', 'bms_license', 'additional_hardware',
        'install_date', 'commencement_date', 'activation_date', 'expiry_date',
        'pc_name', 'pc_make', 'pc_model', 'operating_system', 'os_type',
        'ram', 'cpu_type', 'cpu_speed', 'created_at',
    ]
    search_fields = ['outlet_name', 'anydesk_id', 'teamviewer_id', 'ultraviewer_id', 'pc_name', 'bms_license']
    extra_instructions = (
        "Hardware/software configuration per client outlet. One record per outlet. "
        "Search by AnyDesk ID, outlet name, or PC name to find a client's setup. "
        "platform_type: soundtrack, beatbreeze, bms, dm. system_type: single, multi."
    )


class DeviceQuery(ModelQueryToolset):
    model = Device
    fields = ['id', 'company', 'name', 'device_type', 'model_info', 'notes', 'created_at']
    search_fields = ['name', 'model_info', 'notes']
    extra_instructions = "Devices (PCs, tablets, players) that run music zones. One device can serve multiple zones."


class TicketQuery(ModelQueryToolset):
    model = Ticket
    fields = [
        'id', 'ticket_number', 'subject', 'description', 'status', 'priority',
        'category', 'company', 'contact', 'assigned_to', 'created_at', 'updated_at',
    ]
    search_fields = ['ticket_number', 'subject', 'description']
    extra_instructions = (
        "Support tickets. Status: new, assigned, in_progress, pending, resolved, closed. "
        "Priority: low, medium, high, urgent. Category: technical, billing, zone_config, account, feature_request, general."
    )


class KBArticleQuery(ModelQueryToolset):
    model = KBArticle
    fields = [
        'id', 'article_number', 'title', 'content', 'excerpt', 'status',
        'visibility', 'category', 'created_at', 'updated_at',
    ]
    search_fields = ['title', 'content', 'excerpt', 'article_number']
    extra_instructions = "Knowledge base articles for tech support. Search by keyword to find solutions."


class QuoteLineItemQuery(ModelQueryToolset):
    model = QuoteLineItem
    fields = [
        'id', 'quote', 'product_service', 'description', 'quantity',
        'unit_price', 'discount_percentage', 'tax_rate', 'line_total',
        'created_at', 'updated_at',
    ]
    search_fields = ['description', 'product_service']
    extra_instructions = "Line items attached to quotes. Use to verify what's on a quote PDF or audit nested-write results."


class ContractLineItemQuery(ModelQueryToolset):
    model = ContractLineItem
    fields = [
        'id', 'contract', 'product_service', 'description', 'quantity',
        'unit_price', 'discount_percentage', 'tax_rate', 'line_total',
        'created_at', 'updated_at',
    ]
    search_fields = ['description', 'product_service']
    extra_instructions = "Line items attached to contracts. Use to verify what's on a contract PDF or audit nested-write results."


class ContractServiceLocationQuery(ModelQueryToolset):
    model = ContractServiceLocation
    fields = [
        'id', 'contract', 'location_name', 'platform', 'custom_service_name',
        'sort_order', 'price', 'created_at', 'updated_at',
    ]
    search_fields = ['location_name', 'custom_service_name']
    extra_instructions = (
        "Service-location rows control the product and zone labels on contract PDFs. "
        "platform: soundtrack, beatbreeze, or custom. Update rows individually by ID; "
        "standalone deletion is blocked because omission must never silently erase contract data."
    )


class InvoiceLineItemQuery(ModelQueryToolset):
    model = InvoiceLineItem
    fields = [
        'id', 'invoice', 'product_service', 'description', 'quantity',
        'unit_price', 'tax_rate', 'line_total',
        'service_period_start', 'service_period_end',
        'created_at', 'updated_at',
    ]
    search_fields = ['description', 'product_service']
    extra_instructions = "Line items attached to invoices. Use to verify what's on an invoice PDF or audit nested-write results."


# ============================================================
# Generic CRUD tools — bypasses ViewSet patching bug
# ============================================================
# django-mcp-server v0.5.7 ViewSet integration is broken (patches
# initialize_request at class level, corrupting all API requests).
# These tools use serializers directly — no ViewSet involvement.

import json as _json

_COLLECTION_MAP = {
    'company': (Company, 'crm_app.serializers.CompanySerializer'),
    'contact': (Contact, 'crm_app.serializers.ContactSerializer'),
    'contract': (Contract, 'crm_app.serializers.ContractSerializer'),
    'invoice': (Invoice, 'crm_app.serializers.InvoiceSerializer'),
    'quote': (Quote, 'crm_app.serializers.QuoteSerializer'),
    'opportunity': (Opportunity, 'crm_app.serializers.OpportunitySerializer'),
    'task': (Task, 'crm_app.serializers.TaskSerializer'),
    'zone': (Zone, 'crm_app.serializers.ZoneSerializer'),
    'clienttechdetail': (ClientTechDetail, 'crm_app.serializers.ClientTechDetailSerializer'),
    'device': (Device, 'crm_app.serializers.DeviceSerializer'),
    'ticket': (Ticket, 'crm_app.serializers.TicketSerializer'),
    'kbarticle': (KBArticle, 'crm_app.serializers.KBArticleSerializer'),
    'quotelineitem': (QuoteLineItem, 'crm_app.serializers.QuoteLineItemSerializer'),
    'contractlineitem': (ContractLineItem, 'crm_app.serializers.ContractLineItemSerializer'),
    'servicelocation': (ContractServiceLocation, 'crm_app.serializers.ContractServiceLocationSerializer'),
    'contracttemplate': (ContractTemplate, 'crm_app.serializers.ContractTemplateSerializer'),
    'invoicelineitem': (InvoiceLineItem, 'crm_app.serializers.InvoiceLineItemSerializer'),
}


def _get_serializer_class(dotted_path):
    """Import and return a serializer class from its dotted path."""
    from importlib import import_module
    module_path, class_name = dotted_path.rsplit('.', 1)
    module = import_module(module_path)
    return getattr(module, class_name)


def _dropped_keys(serializer, requested_fields):
    """DRF silently ignores request keys that aren't writable serializer fields — the caller
    gets 'success' while the write never happened (e.g. patching `preamble_template_id` when the
    writable field is `preamble_template`). Surface exactly which keys were dropped and why, so
    agent callers can trust a success response.
    Returns (applied, dropped) where dropped maps key -> reason."""
    applied, dropped = [], {}
    for key in requested_fields:
        f = serializer.fields.get(key)
        if f is None:
            hint = ''
            if key.endswith('_id') and key[:-3] in serializer.fields and not serializer.fields[key[:-3]].read_only:
                hint = f" (did you mean '{key[:-3]}'?)"
            dropped[key] = f"not a field on this collection{hint}"
        elif f.read_only:
            dropped[key] = 'read-only field'
        else:
            applied.append(key)
    return applied, dropped


_GUARDED_CONTRACT_CONTACT_FIELDS = frozenset({
    'customer_contact_name',
    'customer_contact_title',
    'customer_contact_email',
})

_GUARDED_CONTRACT_SERVICE_ITEM_FIELDS = frozenset({'custom_service_items'})
_GUARDED_CONTRACT_SEND_FIELDS = frozenset({'status', 'sent_date'})
# Quote Draft->Sent bookkeeping: same shape and safeguards as contracts (signed receipt).
_GUARDED_QUOTE_SEND_FIELDS = frozenset({'status', 'sent_date'})
_GUARDED_CONTRACT_DATE_FIELDS = frozenset({'start_date', 'end_date'})

# One historical, operator-verified recovery only. The root-owned receipt was
# issued and independently checked for this exact already-sent Premier record.
_PREMIER_SEND_BOOKKEEPING = {
    'record_id': '1941a3bc-9d3b-4161-9d9e-7ff07677f34b',
    'expected_version': '2026-09-08T05:03:57.672476Z',
    'before': {'status': 'Draft', 'sent_date': None},
    'patch': {'status': 'Sent', 'sent_date': '2026-09-09'},
    'contract_number': 'HK-CT261015',
    'verified_receipt_sha256': 'a53e45fad45b0fe841fa0749021ce39aa29eb71ff13e163062350eff7fb733b6',
}

_GUARDED_UPDATE_FIELDS = {
    'contact': {'title', 'department', 'last_contacted'},
    'contract': {
        'customer_signatory_name',
        'customer_signatory_title',
        'additional_customer_signatories',
        *_GUARDED_CONTRACT_CONTACT_FIELDS,
        *_GUARDED_CONTRACT_SERVICE_ITEM_FIELDS,
        *_GUARDED_CONTRACT_SEND_FIELDS,
        *_GUARDED_CONTRACT_DATE_FIELDS,
    },
    'opportunity': {
        'stage', 'last_contact_date', 'follow_up_date', 'expected_close_date',
        'pain_points', 'decision_criteria', 'expected_value', 'probability',
    },
    'ticket': {'priority', 'status'},
    'zone': {'notes'},
    'quote': set(_GUARDED_QUOTE_SEND_FIELDS),
}


def _guarded_scalar(value):
    """Return whether an optimistic-lock value is JSON scalar and finite."""
    if value is None or isinstance(value, (str, bool, int)):
        return True
    return isinstance(value, float) and value == value and value not in (float('inf'), float('-inf'))


def _strict_scalar_equal(left, right):
    """Avoid Python's bool/int equality and never coerce expected CRM values."""
    return type(left) is type(right) and left == right


def _guarded_json_value(value):
    """Accept only recursively finite JSON values for optimistic locks."""
    if _guarded_scalar(value):
        return True
    if isinstance(value, list):
        return all(_guarded_json_value(item) for item in value)
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and _guarded_json_value(item)
            for key, item in value.items()
        )
    return False


def _strict_json_equal(left, right):
    """Compare nested JSON without bool/int coercion or list reordering."""
    if type(left) is not type(right):
        return False
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _strict_json_equal(left_item, right_item)
            for left_item, right_item in zip(left, right)
        )
    if isinstance(left, dict):
        return set(left) == set(right) and all(
            _strict_json_equal(left[key], right[key]) for key in left
        )
    return _strict_scalar_equal(left, right)


def _guarded_json_object(raw):
    """Parse a guarded payload without accepting duplicate keys or non-finite values."""
    def reject_constant(value):
        raise ValueError(f'non-finite JSON value: {value}')

    def reject_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result

    value = _json.loads(raw, parse_constant=reject_constant, object_pairs_hook=reject_duplicates)
    if not isinstance(value, dict):
        raise ValueError('JSON object required')
    return value


def _guarded_version(value):
    """Normalize an RFC3339 timestamp, rejecting naive or malformed values."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value[:-1] + '+00:00' if value.endswith('Z') else value)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _guarded_commercial_authorization(collection, record_id, fields, raw):
    """Require an exact user-authorization binding for commercial closures."""
    sensitive = collection == 'opportunity' and (
        bool({'expected_value', 'probability'} & set(fields))
        or fields.get('stage') in {'Won', 'Lost'}
    )
    if not sensitive:
        return None

    try:
        context = _guarded_json_object(raw)
    except (TypeError, ValueError, _json.JSONDecodeError):
        return 'Commercial opportunity update requires explicit authorization context.'
    if not context:
        return 'Commercial opportunity update requires explicit authorization context.'

    required = {'kind', 'source_thread_id', 'record_id', 'authorized_changes'}
    if set(context) != required:
        return 'Commercial authorization context must contain exactly the required fields.'
    if context.get('kind') != 'explicit_user_commercial':
        return 'Commercial authorization kind is invalid.'
    if not isinstance(context.get('source_thread_id'), str) or not context['source_thread_id'].strip():
        return 'Commercial authorization requires a source thread ID.'
    if context.get('record_id') != str(record_id):
        return 'Commercial authorization is bound to a different record.'
    authorized_changes = context.get('authorized_changes')
    if not isinstance(authorized_changes, dict) or authorized_changes != fields:
        return 'Commercial authorization does not exactly match the requested patch.'
    if any(not _guarded_scalar(value) for value in authorized_changes.values()):
        return 'Commercial authorization values must be finite JSON scalars or null.'
    return None


def _guarded_contract_contact_authorization(record_id, fields, raw):
    """Bind a complete Draft-contract contact correction to its user source."""
    if set(fields) != _GUARDED_CONTRACT_CONTACT_FIELDS:
        return 'Contract contact correction must include name, title, and email only.'
    try:
        context = _guarded_json_object(raw)
    except (TypeError, ValueError, _json.JSONDecodeError):
        return 'Contract contact correction requires explicit authorization context.'
    required = {'kind', 'source_reference', 'record_id', 'authorized_changes'}
    if set(context) != required or context.get('kind') != 'explicit_user_contract_contact':
        return 'Contract contact authorization context is invalid.'
    if not isinstance(context.get('source_reference'), str) or not context['source_reference'].strip():
        return 'Contract contact authorization requires a source reference.'
    if context.get('record_id') != str(record_id):
        return 'Contract contact authorization is bound to a different record.'
    if not _strict_json_equal(context.get('authorized_changes'), fields):
        return 'Contract contact authorization does not exactly match the requested patch.'
    return None


def _guarded_contract_service_item_authorization(record_id, fields, raw):
    """Require one source-bound, well-shaped Draft service-item replacement."""
    if set(fields) != _GUARDED_CONTRACT_SERVICE_ITEM_FIELDS:
        return 'Contract service-item correction must contain custom_service_items only.'
    try:
        context = _guarded_json_object(raw)
    except (TypeError, ValueError, _json.JSONDecodeError):
        return 'Contract service-item correction requires explicit authorization context.'
    required = {'kind', 'source_reference', 'record_id', 'authorized_changes'}
    if set(context) != required or context.get('kind') != 'explicit_user_contract_service_items':
        return 'Contract service-item authorization context is invalid.'
    if not isinstance(context.get('source_reference'), str) or not context['source_reference'].strip():
        return 'Contract service-item authorization requires a source reference.'
    if context.get('record_id') != str(record_id):
        return 'Contract service-item authorization is bound to a different record.'
    if not _strict_json_equal(context.get('authorized_changes'), fields):
        return 'Contract service-item authorization does not exactly match the requested patch.'
    items = fields['custom_service_items']
    if not isinstance(items, list) or any(
        not isinstance(item, dict)
        or set(item) != {'name', 'description'}
        or not all(isinstance(item[key], str) for key in ('name', 'description'))
        or not (item['name'].strip() or item['description'].strip())
        for item in items
    ):
        return 'Contract service items must be an array of non-empty name/description objects.'
    return None


def _guarded_contract_send_authorization(record_id, fields, before, expected_version, raw):
    """Authorize exact Sent/date bookkeeping with a signed or Premier receipt.

    The signed route independently verifies Theo's protected attestation at
    the CRM boundary. It does not itself query Gmail, Chat, or frozen PDFs.
    Return (error, verified_signed_receipt_or_none).
    """
    if set(fields) != _GUARDED_CONTRACT_SEND_FIELDS:
        return 'Contract send bookkeeping must contain status and sent_date only.', None
    if fields.get('status') != 'Sent':
        return 'Contract send bookkeeping can only record Sent status.', None
    sent_date = fields.get('sent_date')
    if not isinstance(sent_date, str):
        return 'Contract send bookkeeping requires an ISO calendar sent_date.', None
    try:
        if date.fromisoformat(sent_date).isoformat() != sent_date:
            raise ValueError('non-canonical date')
    except ValueError:
        return 'Contract send bookkeeping requires an ISO calendar sent_date.', None
    if not _strict_json_equal(before, {'status': 'Draft', 'sent_date': None}):
        return 'Contract send bookkeeping requires exact Draft/null before values.', None
    try:
        context = _guarded_json_object(raw)
    except (TypeError, ValueError, _json.JSONDecodeError):
        return 'Contract send bookkeeping requires verified authorization context.', None
    if context.get('kind') == 'signed_contract_send_bookkeeping':
        try:
            verified = verify_signed_contract_send_context(
                context, record_id=record_id, fields=fields, before=before,
                expected_version=expected_version,
            )
        except ReceiptVerificationError as exc:
            return str(exc), None
        return None, verified

    # Historical one-record recovery remains pinned and cannot authorize a new
    # contract. Its root receipt was independently checked by Cira at the time.
    pinned = _PREMIER_SEND_BOOKKEEPING
    if (str(record_id) != pinned['record_id']
            or _guarded_version(expected_version) != _guarded_version(pinned['expected_version'])
            or not _strict_json_equal(before, pinned['before'])
            or not _strict_json_equal(fields, pinned['patch'])):
        return 'Contract send bookkeeping is not the approved Premier recovery.', None
    if not isinstance(pinned['verified_receipt_sha256'], str) or not re.fullmatch(
        r'[0-9a-f]{64}', pinned['verified_receipt_sha256']
    ):
        return 'Contract send bookkeeping operator receipt is not configured.', None
    required = {
        'kind', 'source_reference', 'record_id', 'authorized_changes',
        'verified_receipt_sha256', 'contract_number',
    }
    if set(context) != required or context.get('kind') != 'verified_contract_send_bookkeeping':
        return 'Contract send bookkeeping authorization context is invalid.', None
    if not isinstance(context.get('source_reference'), str) or not context['source_reference'].strip():
        return 'Contract send bookkeeping requires a source reference.', None
    if context.get('record_id') != str(record_id):
        return 'Contract send bookkeeping is bound to a different record.', None
    if not _strict_json_equal(context.get('authorized_changes'), fields):
        return 'Contract send bookkeeping authorization does not match the patch.', None
    if not isinstance(context.get('verified_receipt_sha256'), str) or not re.fullmatch(
        r'[0-9a-f]{64}', context['verified_receipt_sha256']
    ) or context['verified_receipt_sha256'] != pinned['verified_receipt_sha256']:
        return 'Contract send bookkeeping requires a verified receipt digest.', None
    if not isinstance(context.get('contract_number'), str) or not re.fullmatch(
        r'(?:HK|TH)-CT[0-9]{5,}', context['contract_number']
    ) or context['contract_number'] != pinned['contract_number']:
        return 'Contract send bookkeeping requires an existing final contract number.', None
    return None, None


def _guarded_quote_send_authorization(record_id, fields, before, expected_version, raw):
    """Authorize exact quote Sent/date bookkeeping with a quote-attestor signed receipt.

    Return (error, verified_signed_receipt_or_none). There is no unsigned or
    pinned-recovery route for quotes.
    """
    if set(fields) != _GUARDED_QUOTE_SEND_FIELDS:
        return 'Quote send bookkeeping must contain status and sent_date only.', None
    if fields.get('status') != 'Sent':
        return 'Quote send bookkeeping can only record Sent status.', None
    if not _strict_json_equal(before, {'status': 'Draft', 'sent_date': None}):
        return 'Quote send bookkeeping requires exact Draft/null before values.', None
    try:
        context = _guarded_json_object(raw)
    except (TypeError, ValueError, _json.JSONDecodeError):
        return 'Quote send bookkeeping requires a signed send receipt.', None
    try:
        verified = verify_signed_quote_send_context(
            context, record_id=record_id, fields=fields, before=before,
            expected_version=expected_version,
        )
    except QuoteReceiptVerificationError as exc:
        return str(exc), None
    return None, verified


def _guarded_contract_date_authorization(fields, raw):
    """Accept provenance for a bounded Sent-but-unsigned date correction.

    Cira authenticates the writer and verifies the sender before forwarding;
    this context records that source, not a new owner-approval requirement.
    """
    if not set(fields) or not set(fields).issubset(_GUARDED_CONTRACT_DATE_FIELDS):
        return 'Contract date correction may change start_date or end_date only.', None
    try:
        context = _guarded_json_object(raw)
    except (TypeError, ValueError, _json.JSONDecodeError):
        return 'Contract date correction requires structured source context.', None
    if set(context) != {'kind', 'requested_by', 'source_reference', 'reason'}:
        return 'Contract date correction source context has unexpected fields.', None
    if context.get('kind') != 'routine_contract_date_correction':
        return 'Contract date correction source kind is invalid.', None
    if (not isinstance(context.get('requested_by'), str)
            or context['requested_by'] not in {'norbert', 'lyra', 'theo'}):
        return 'Contract date correction requester is invalid.', None
    for name, limit in (('source_reference', 512), ('reason', 1000)):
        value = context.get(name)
        if (not isinstance(value, str) or not 1 <= len(value) <= limit
                or value.strip() != value or not value.isprintable()):
            return f'Contract date correction {name} is invalid.', None
    for value in fields.values():
        if not isinstance(value, str):
            return 'Contract date correction requires ISO calendar dates.', None
        try:
            if date.fromisoformat(value).isoformat() != value:
                raise ValueError('non-canonical date')
        except ValueError:
            return 'Contract date correction requires ISO calendar dates.', None
    return None, context


@mcp_server.tool()
def create_record(collection: str, data: str) -> str:
    """Create a new record in a CRM collection.

    Args:
        collection: Collection name (company, contact, contract, invoice, quote,
                    opportunity, task, zone, clienttechdetail, device, ticket, kbarticle,
                    quotelineitem, contractlineitem, servicelocation, invoicelineitem,
                    contracttemplate)
        data: JSON string with field values. Use query_data_collections to check
              field names and valid choices first.

    Returns: JSON with the created record's id and key fields, or validation errors.
    """
    if collection not in _COLLECTION_MAP:
        return f"Error: Unknown collection '{collection}'. Valid: {', '.join(sorted(_COLLECTION_MAP))}"
    _agent_gate.observe(tool='create_record', verb='create', collection=collection, data=data)

    try:
        fields = _json.loads(data)
    except _json.JSONDecodeError as e:
        return f"Error: Invalid JSON — {e}"

    if collection == 'quote' and isinstance(fields, dict) and (
        fields.get('status') == 'Sent' or 'sent_date' in fields
    ):
        return _json.dumps({
            'created': False,
            'error': 'Quotes are created as Draft; record Sent through the signed quote-send receipt path.',
        })

    model, serializer_path = _COLLECTION_MAP[collection]
    SerializerClass = _get_serializer_class(serializer_path)

    serializer = SerializerClass(data=fields)
    _, dropped = _dropped_keys(serializer, fields)
    if collection == 'contract' and dropped:
        return _json.dumps({
            'created': False,
            'error': 'Contract fields were not writable; nothing was saved.',
            'ignored_keys': dropped,
        })
    if not serializer.is_valid():
        return f"Validation errors: {_json.dumps(serializer.errors)}"

    instance = serializer.save()
    # Return a concise summary
    result = {'id': str(instance.id)}
    for attr in ['name', 'contract_number', 'invoice_number', 'quote_number',
                 'ticket_number', 'article_number', 'title', 'email', 'subject']:
        if hasattr(instance, attr) and getattr(instance, attr):
            result[attr] = str(getattr(instance, attr))
    if collection in {'quote', 'contract', 'invoice'}:
        result['billing_entity'] = instance.billing_entity
        result['effective_billing_entity'] = instance.effective_billing_entity
    _, dropped = _dropped_keys(serializer, fields)
    if dropped:
        result['warning_ignored_keys'] = dropped
        result['warning'] = ('These keys were NOT saved (DRF drops non-writable keys silently). '
                             'Fix the key names and re-send if you intended to set them.')
    return _json.dumps(result)


@mcp_server.tool()
def update_record(
    collection: str,
    id: str,
    data: str,
    expected_version: str = '',
    expected_values: str = '{}',
    authorization_context: str = '{}',
) -> str:
    """Update an existing record in a CRM collection.

    Args:
        collection: Collection name (same options as create_record)
        id: UUID of the record to update
        data: JSON string with fields to update (partial update — only include
              fields you want to change). For an atomic full replacement of a
              contract's service locations, include replace_service_locations=true,
              the complete intended service_locations array, and matching pricing
              fields in this one update. Without that flag, omitted locations are
              preserved.
        expected_version: Optional exact current serializer `updated_at` value for
              guarded low-risk corrections. Supplying it requires expected_values.
        expected_values: JSON object containing the currently observed values
              for exactly the fields in data. Values may be finite JSON
              scalars/null or nested arrays/objects. Guarded updates are limited
              to contact title/department/last_contacted, Draft contract
              customer contact details, customer signatories, custom service
              items, verified already-sent status/date bookkeeping, and
              source-verified dates on an unsigned Sent contract;
              opportunity stage/date and qualification/value fields,
              ticket priority/status, and zone notes.
        authorization_context: Exact explicit-user authorization binding required
              for opportunity value/probability changes, terminal Won/Lost
              transitions, and Draft contract customer contact or service-item
              corrections.
              Contract contact corrections require kind=explicit_user_contract_contact,
              a source_reference, record_id, and the complete authorized_changes.
              Service-item corrections use kind=explicit_user_contract_service_items
              with the same exact source, record and patch binding.
              The historical Premier recovery uses
              kind=verified_contract_send_bookkeeping and its pinned operator
              receipt digest. General already-sent bookkeeping requires
              kind=signed_contract_send_bookkeeping and the complete
              Theo-root-signed receipt envelope. The CRM verifies its Ed25519
              signature, exact patch/version/before/number binding and expiry;
              the protected signer attests provider and approval evidence.
              Sent-contract term corrections use
              kind=routine_contract_date_correction with requested_by,
              source_reference, and reason.
              This tool never sends email.
              Routine metadata corrections leave this as the default empty object.

    Returns: JSON with updated fields, or validation errors.
    """
    if collection not in _COLLECTION_MAP:
        return f"Error: Unknown collection '{collection}'. Valid: {', '.join(sorted(_COLLECTION_MAP))}"
    _agent_gate.observe(tool='update_record', verb='update', collection=collection, record_id=id,
                        data=data, expected_version=expected_version, expected_values=expected_values,
                        authorization_context=authorization_context)

    # The original three-argument API remains deliberately unchanged.  The
    # optimistic path is opt-in and only permits the small correction surface
    # that a reviewer can re-read immediately after saving.
    guarded = bool(expected_version) or expected_values != '{}'
    # The generic three-argument MCP path must not bypass the signed receipt
    # boundary for Sent/date bookkeeping. Other contract operations retain
    # their existing behavior.
    if collection == 'contract' and not guarded:
        try:
            unguarded_fields = _guarded_json_object(data)
        except (TypeError, ValueError, _json.JSONDecodeError):
            unguarded_fields = {}
        if unguarded_fields.get('status') == 'Sent' or 'sent_date' in unguarded_fields:
            return _json.dumps({
                'updated': False, 'id': str(id),
                'error': 'Contract status/date MCP changes require guarded send authorization.',
            })
    if collection == 'quote' and not guarded:
        try:
            unguarded_fields = _guarded_json_object(data)
        except (TypeError, ValueError, _json.JSONDecodeError):
            unguarded_fields = {}
        if unguarded_fields.get('status') == 'Sent' or 'sent_date' in unguarded_fields:
            return _json.dumps({
                'updated': False, 'id': str(id),
                'error': 'Quote status/date MCP changes require guarded send authorization.',
            })
    signed_send_receipt = None
    signed_quote_receipt = None
    contract_date_context = None
    if guarded:
        try:
            fields = _guarded_json_object(data)
        except (TypeError, ValueError, _json.JSONDecodeError):
            return _json.dumps({'updated': False, 'id': str(id), 'error': 'Guarded patch must be a non-empty JSON object.'})
        if not fields:
            return _json.dumps({'updated': False, 'id': str(id), 'error': 'Guarded patch must be a non-empty JSON object.'})
        if not isinstance(expected_version, str) or not expected_version:
            return _json.dumps({'updated': False, 'id': str(id), 'error': 'Guarded update requires a non-empty expected_version.'})
        try:
            before = _guarded_json_object(expected_values)
        except (TypeError, ValueError, _json.JSONDecodeError):
            return _json.dumps({'updated': False, 'id': str(id), 'error': 'Guarded expected_values must be a JSON object.'})
        if set(before) != set(fields):
            return _json.dumps({'updated': False, 'id': str(id), 'error': 'Guarded expected_values keys must exactly match patch keys.'})
        if any(not _guarded_json_value(value) for value in fields.values()) or any(
            not _guarded_json_value(value) for value in before.values()
        ):
            return _json.dumps({'updated': False, 'id': str(id), 'error': 'Guarded values must be finite JSON values.'})
        # Status alone remains outside the correction lane. The signed send
        # route requires the exact status/date pair, so keep the old refusal
        # for a status-only patch before considering receipt authorization.
        if collection in ('contract', 'quote') and set(fields) == {'status'}:
            return _json.dumps({'updated': False, 'id': str(id), 'error': 'Guarded patch contains fields outside the approved correction scope.'})
        allowed = _GUARDED_UPDATE_FIELDS.get(collection)
        if allowed is None or not set(fields).issubset(allowed):
            return _json.dumps({'updated': False, 'id': str(id), 'error': 'Guarded patch contains fields outside the approved correction scope.'})
        authorization_error = _guarded_commercial_authorization(
            collection, id, fields, authorization_context,
        )
        if authorization_error:
            return _json.dumps({'updated': False, 'id': str(id), 'error': authorization_error})
        if collection == 'contract' and set(fields) & _GUARDED_CONTRACT_CONTACT_FIELDS:
            authorization_error = _guarded_contract_contact_authorization(
                id, fields, authorization_context,
            )
            if authorization_error:
                return _json.dumps({'updated': False, 'id': str(id), 'error': authorization_error})
        if collection == 'contract' and set(fields) & _GUARDED_CONTRACT_SERVICE_ITEM_FIELDS:
            authorization_error = _guarded_contract_service_item_authorization(
                id, fields, authorization_context,
            )
            if authorization_error:
                return _json.dumps({'updated': False, 'id': str(id), 'error': authorization_error})
        if collection == 'contract' and set(fields) & _GUARDED_CONTRACT_SEND_FIELDS:
            authorization_error, signed_send_receipt = _guarded_contract_send_authorization(
                id, fields, before, expected_version, authorization_context,
            )
            if authorization_error:
                return _json.dumps({'updated': False, 'id': str(id), 'error': authorization_error})
        if collection == 'quote' and set(fields) & _GUARDED_QUOTE_SEND_FIELDS:
            authorization_error, signed_quote_receipt = _guarded_quote_send_authorization(
                id, fields, before, expected_version, authorization_context,
            )
            if authorization_error:
                return _json.dumps({'updated': False, 'id': str(id), 'error': authorization_error})
        if collection == 'contract' and set(fields) & _GUARDED_CONTRACT_DATE_FIELDS:
            authorization_error, contract_date_context = _guarded_contract_date_authorization(
                fields, authorization_context,
            )
            if authorization_error:
                return _json.dumps({'updated': False, 'id': str(id), 'error': authorization_error})
    else:
        try:
            fields = _json.loads(data)
        except _json.JSONDecodeError as e:
            return f"Error: Invalid JSON — {e}"

    model, serializer_path = _COLLECTION_MAP[collection]

    if guarded:
        SerializerClass = _get_serializer_class(serializer_path)
        with transaction.atomic():
            try:
                instance = model.objects.select_for_update().get(id=id)
            except model.DoesNotExist:
                return f"Error: {collection} with ID '{id}' not found."

            if contract_date_context:
                if instance.status != 'Sent':
                    return _json.dumps({
                        'updated': False, 'id': str(id),
                        'error': 'Contract date correction requires Sent status; nothing was saved.',
                    })
                if instance.contract_documents.filter(
                    Q(is_signed=True) | Q(signed_date__isnull=False)
                ).exists():
                    return _json.dumps({
                        'updated': False, 'id': str(id),
                        'error': 'Signed contract document blocks routine date correction; nothing was saved.',
                    })
                start_date = date.fromisoformat(fields['start_date']) if 'start_date' in fields else instance.start_date
                end_date = date.fromisoformat(fields['end_date']) if 'end_date' in fields else instance.end_date
                if start_date is None or end_date is None or start_date > end_date:
                    return _json.dumps({
                        'updated': False, 'id': str(id),
                        'error': 'Contract date correction requires a complete ordered interval; nothing was saved.',
                    })
                original_identity = (instance.company_id, instance.contract_number, instance.status, instance.sent_date)

            if collection == 'contract' and set(fields) & _GUARDED_CONTRACT_CONTACT_FIELDS:
                if instance.status != 'Draft':
                    return _json.dumps({
                        'updated': False, 'id': str(id),
                        'error': 'Contract contact correction requires Draft status; nothing was saved.',
                    })

            if collection == 'contract' and set(fields) & _GUARDED_CONTRACT_SERVICE_ITEM_FIELDS:
                if instance.status != 'Draft':
                    return _json.dumps({
                        'updated': False, 'id': str(id),
                        'error': 'Contract service-item correction requires Draft status; nothing was saved.',
                    })

            if collection == 'contract' and set(fields) & _GUARDED_CONTRACT_SEND_FIELDS:
                bound_number = (
                    signed_send_receipt['payload']['contract_number']
                    if signed_send_receipt else
                    _guarded_json_object(authorization_context)['contract_number']
                )
                if signed_send_receipt:
                    payload = signed_send_receipt['payload']
                    receipt_sha = signed_send_receipt['receipt_sha256']
                    uses = list(ContractSendReceiptUse.objects.select_for_update().filter(
                        Q(request_key=payload['request_key'])
                        | Q(nonce=payload['nonce'])
                        | Q(receipt_sha256=receipt_sha)
                    )[:3])
                    if uses:
                        same_use = len(uses) == 1 and all((
                            uses[0].contract_id == instance.pk,
                            uses[0].request_key == payload['request_key'],
                            str(uses[0].nonce) == payload['nonce'],
                            uses[0].receipt_sha256 == receipt_sha,
                            uses[0].key_id == payload['key_id'],
                            uses[0].contract_number == bound_number,
                            uses[0].sent_date.isoformat() == fields['sent_date'],
                            uses[0].before_version == expected_version,
                        ))
                        current = SerializerClass(instance).data
                        if same_use and all((
                            instance.status == 'Sent',
                            instance.sent_date is not None,
                            instance.sent_date is not None
                            and instance.sent_date.isoformat() == fields['sent_date'],
                            instance.contract_number == bound_number,
                            current.get('updated_at') == uses[0].after_version,
                        )):
                            return _json.dumps({
                                'updated': False, 'already_applied': True,
                                'id': str(id), 'applied': fields,
                                'contract_number': bound_number,
                                'receipt_sha256': receipt_sha,
                                'request_key': payload['request_key'],
                                'post_version': uses[0].after_version,
                            })
                        return _json.dumps({
                            'updated': False, 'id': str(id),
                            'error': 'Contract send receipt request, nonce, or state conflicts; nothing was saved.',
                        })
                if (instance.status != 'Draft' or instance.sent_date is not None
                        or instance.contract_number != bound_number):
                    return _json.dumps({
                        'updated': False, 'id': str(id),
                        'error': 'Contract send bookkeeping requires the same Draft/null record and final number; nothing was saved.',
                    })

            if signed_quote_receipt:
                quote_payload = signed_quote_receipt['payload']
                quote_receipt_sha = signed_quote_receipt['receipt_sha256']
                quote_number = quote_payload['quote_number']
                uses = list(QuoteSendReceiptUse.objects.select_for_update().filter(
                    Q(request_key=quote_payload['request_key'])
                    | Q(nonce=quote_payload['nonce'])
                    | Q(receipt_sha256=quote_receipt_sha)
                )[:3])
                if uses:
                    same_use = len(uses) == 1 and all((
                        uses[0].quote_id == instance.pk,
                        uses[0].request_key == quote_payload['request_key'],
                        str(uses[0].nonce) == quote_payload['nonce'],
                        uses[0].receipt_sha256 == quote_receipt_sha,
                        uses[0].key_id == quote_payload['key_id'],
                        uses[0].quote_number == quote_number,
                        uses[0].mailbox == quote_payload['mailbox'],
                        uses[0].sent_date.isoformat() == fields['sent_date'],
                        uses[0].before_version == expected_version,
                    ))
                    current = SerializerClass(instance).data
                    if same_use and all((
                        instance.status == 'Sent',
                        instance.sent_date is not None
                        and instance.sent_date.isoformat() == fields['sent_date'],
                        instance.quote_number == quote_number,
                        current.get('updated_at') == uses[0].after_version,
                    )):
                        return _json.dumps({
                            'updated': False, 'already_applied': True,
                            'id': str(id), 'applied': fields,
                            'quote_number': quote_number,
                            'receipt_sha256': quote_receipt_sha,
                            'request_key': quote_payload['request_key'],
                            'post_version': uses[0].after_version,
                        })
                    return _json.dumps({
                        'updated': False, 'id': str(id),
                        'error': 'Quote send receipt request, nonce, or state conflicts; nothing was saved.',
                    })
                if (instance.status != 'Draft' or instance.sent_date is not None
                        or instance.quote_number != quote_number):
                    return _json.dumps({
                        'updated': False, 'id': str(id),
                        'error': 'Quote send bookkeeping requires the same Draft/null record and number; nothing was saved.',
                    })

            current = SerializerClass(instance).data
            expected_instant = _guarded_version(expected_version)
            current_instant = _guarded_version(current.get('updated_at'))
            if expected_instant is None or current_instant is None or current_instant != expected_instant:
                return _json.dumps({
                    'updated': False, 'id': str(id), 'error': 'Stale expected_version; nothing was saved.',
                })
            if any(
                key not in current or not _strict_json_equal(current[key], value)
                for key, value in before.items()
            ):
                return _json.dumps({
                    'updated': False, 'id': str(id), 'error': 'Expected values no longer match; nothing was saved.',
                })

            serializer = SerializerClass(instance, data=fields, partial=True)
            applied, dropped = _dropped_keys(serializer, fields)
            # An allowlist is not a substitute for checking the actual current
            # serializer: a renamed/read-only field must fail closed, never drop.
            if dropped or set(applied) != set(fields):
                return _json.dumps({
                    'updated': False, 'id': str(id),
                    'error': 'Guarded patch contains non-writable fields; nothing was saved.',
                    'ignored_keys': dropped,
                })
            if not serializer.is_valid():
                return f"Validation errors: {_json.dumps(serializer.errors)}"

            instance = serializer.save()
            if contract_date_context:
                # Read the persisted row independently before committing the
                # date change and its audit entry. No number, status, company,
                # or send bookkeeping may change as a side effect.
                instance = model.objects.get(id=id)
                readback = SerializerClass(instance).data
                if (original_identity != (
                    instance.company_id, instance.contract_number,
                    instance.status, instance.sent_date,
                ) or not readback.get('updated_at') or any(
                    readback.get(key) != value for key, value in fields.items()
                ) or instance.contract_documents.filter(
                    Q(is_signed=True) | Q(signed_date__isnull=False)
                ).exists()):
                    transaction.set_rollback(True)
                    return _json.dumps({
                        'updated': False, 'id': str(id),
                        'error': 'Contract date correction readback or signed state changed; nothing was saved.',
                    })
                audit = AuditLog.objects.create(
                    action='UPDATE', model_name='Contract', record_id=str(id),
                    changes={
                        key: {'before': before[key], 'after': fields[key]}
                        for key in fields
                    },
                    additional_data={
                        'kind': contract_date_context['kind'],
                        'requested_by': contract_date_context['requested_by'],
                        'source_reference': contract_date_context['source_reference'],
                        'reason': contract_date_context['reason'],
                        'company_id': str(instance.company_id),
                        'contract_number': instance.contract_number,
                        'expected_version': expected_version,
                        'post_version': readback['updated_at'],
                    },
                )
            if collection == 'contract' and set(fields) == _GUARDED_CONTRACT_SEND_FIELDS:
                if instance.contract_number != bound_number:
                    transaction.set_rollback(True)
                    return _json.dumps({
                        'updated': False, 'id': str(id),
                        'error': 'Contract number changed during send bookkeeping; nothing was saved.',
                    })
                if signed_send_receipt:
                    # Read the row back independently from the serializer before
                    # committing either the contract update or its unique ledger.
                    instance = model.objects.get(id=id)
                    readback = SerializerClass(instance).data
                    if not all((
                        instance.status == 'Sent',
                        instance.sent_date is not None,
                        instance.sent_date is not None
                        and instance.sent_date.isoformat() == fields['sent_date'],
                        instance.contract_number == bound_number,
                        readback.get('updated_at'),
                    )):
                        transaction.set_rollback(True)
                        return _json.dumps({
                            'updated': False, 'id': str(id),
                            'error': 'Contract send readback did not match; nothing was saved.',
                        })
                    payload = signed_send_receipt['payload']
                    try:
                        ContractSendReceiptUse.objects.create(
                            contract=instance,
                            request_key=payload['request_key'],
                            nonce=payload['nonce'],
                            receipt_sha256=signed_send_receipt['receipt_sha256'],
                            key_id=payload['key_id'],
                            contract_number=bound_number,
                            sent_date=instance.sent_date,
                            before_version=expected_version,
                            after_version=readback['updated_at'],
                        )
                    except IntegrityError:
                        transaction.set_rollback(True)
                        return _json.dumps({
                            'updated': False, 'id': str(id),
                            'error': 'Contract send receipt was used concurrently; nothing was saved.',
                        })
            if signed_quote_receipt:
                # Independent readback before committing the quote update and its
                # unique receipt ledger row (same transaction).
                instance = model.objects.get(id=id)
                readback = SerializerClass(instance).data
                if not all((
                    instance.status == 'Sent',
                    instance.sent_date is not None
                    and instance.sent_date.isoformat() == fields['sent_date'],
                    instance.quote_number == signed_quote_receipt['payload']['quote_number'],
                    readback.get('updated_at'),
                )):
                    transaction.set_rollback(True)
                    return _json.dumps({
                        'updated': False, 'id': str(id),
                        'error': 'Quote send readback did not match; nothing was saved.',
                    })
                quote_payload = signed_quote_receipt['payload']
                try:
                    QuoteSendReceiptUse.objects.create(
                        quote=instance,
                        request_key=quote_payload['request_key'],
                        nonce=quote_payload['nonce'],
                        receipt_sha256=signed_quote_receipt['receipt_sha256'],
                        key_id=quote_payload['key_id'],
                        quote_number=quote_payload['quote_number'],
                        mailbox=quote_payload['mailbox'],
                        sent_date=instance.sent_date,
                        before_version=expected_version,
                        after_version=readback['updated_at'],
                    )
                except IntegrityError:
                    transaction.set_rollback(True)
                    return _json.dumps({
                        'updated': False, 'id': str(id),
                        'error': 'Quote send receipt was used concurrently; nothing was saved.',
                    })
            persisted = {}
            for key in applied:
                src = serializer.fields[key].source or key
                val = getattr(instance, src, None)
                persisted[key] = val if isinstance(val, (list, dict)) else (
                    str(val) if val is not None else None
                )
            result = {'updated': True, 'id': str(id), 'applied': persisted}
            if collection == 'contract' and set(fields) == _GUARDED_CONTRACT_SEND_FIELDS:
                result['contract_number'] = instance.contract_number
                if signed_send_receipt:
                    result.update({
                        'receipt_sha256': signed_send_receipt['receipt_sha256'],
                        'request_key': signed_send_receipt['payload']['request_key'],
                        'post_version': readback['updated_at'],
                    })
            if contract_date_context:
                result.update({
                    'company_id': str(instance.company_id),
                    'contract_number': instance.contract_number,
                    'post_version': readback['updated_at'],
                    'audit_log_id': str(audit.pk),
                })
            return _json.dumps(result, default=str)

    try:
        instance = model.objects.get(id=id)
    except model.DoesNotExist:
        return f"Error: {collection} with ID '{id}' not found."

    if (collection == 'contract' and instance.status == 'Sent'
            and {'start_date', 'end_date'} & set(fields)):
        return _json.dumps({
            'updated': False, 'id': str(id),
            'error': 'Sent-contract dates require guarded correction authorization; nothing was saved.',
        })

    SerializerClass = _get_serializer_class(serializer_path)
    serializer = SerializerClass(instance, data=fields, partial=True)
    _, dropped = _dropped_keys(serializer, fields)
    if collection == 'contract' and dropped:
        return _json.dumps({
            'updated': False, 'id': str(id),
            'error': 'Contract fields were not writable; nothing was saved.',
            'ignored_keys': dropped,
        })
    if not serializer.is_valid():
        return f"Validation errors: {_json.dumps(serializer.errors)}"

    applied, dropped = _dropped_keys(serializer, fields)
    if not applied:
        # Nothing in the patch is writable -> refuse rather than fake success.
        return _json.dumps({
            'updated': False, 'id': str(id),
            'error': 'No writable fields in patch — nothing was saved.',
            'ignored_keys': dropped,
        })

    instance = serializer.save()
    # Read-back so the caller can verify what was actually persisted.
    persisted = {}
    for key in applied:
        if collection == 'contract' and key == 'service_locations':
            from crm_app.serializers import ContractServiceLocationSerializer
            locations = instance.service_locations.order_by('sort_order', 'id')
            persisted[key] = ContractServiceLocationSerializer(
                locations,
                many=True,
            ).data
            continue
        if collection == 'contract' and key == 'replace_service_locations':
            # This is a write-only operation mode, not a model attribute. Echo the
            # accepted value so the caller can verify which semantics were applied.
            persisted[key] = bool(fields[key])
            continue
        src = serializer.fields[key].source or key
        val = getattr(instance, src, None)
        persisted[key] = str(val) if val is not None else None
    result = {'updated': True, 'id': str(id), 'applied': persisted}
    if dropped:
        result['warning_ignored_keys'] = dropped
        result['warning'] = ('These keys were NOT saved (DRF drops non-writable keys silently). '
                             'Fix the key names and re-send if you intended to set them.')
    return _json.dumps(result, default=str)


@mcp_server.tool()
def get_commercial_document_context(collection: str, id: str) -> str:
    """Read a quote/contract/invoice and its precise writable tailoring fields.

    Side-effect-free: does not save, reserve a number, change status, or render.
    The returned record includes billing_entity (override) and
    effective_billing_entity (resolved issuer). A blank override follows the
    Company default; currency and customer country never choose the issuer.
    Use field names from writable_fields for an explicitly authorized change.
    Internal notes are CRM-only and are not customer-facing clauses.
    """
    if collection not in {'quote', 'contract', 'invoice'}:
        return _json.dumps({'error': 'collection must be quote, contract or invoice.'})
    model, serializer_path = _COLLECTION_MAP[collection]
    from django.core.exceptions import ValidationError
    try:
        instance = model.objects.select_related('company').get(id=id)
        serializer = _get_serializer_class(serializer_path)(instance)
        result = {
            'collection': collection,
            'record': serializer.data,
            'company_default_billing_entity': instance.company.billing_entity,
            'customer_country': instance.company.country,
            'writable_fields': sorted(
                name for name, field in serializer.fields.items() if not field.read_only
            ),
        }
        if collection == 'contract':
            from crm_app.services.document_context import contract_tailoring_context
            result['tailoring'] = contract_tailoring_context(instance)
        return _json.dumps(result, default=str)
    except model.DoesNotExist:
        return _json.dumps({'error': f"{collection} '{id}' not found."})
    except (TypeError, ValueError, ValidationError) as exc:
        return _json.dumps({'error': 'clarification_required', 'detail': str(exc)})


@mcp_server.tool()
def delete_record(collection: str, id: str) -> str:
    """Delete a record from a CRM collection.

    Args:
        collection: Collection name (same options as create_record)
        id: UUID of the record to delete

    Returns: Confirmation message or error.
    """
    if collection not in _COLLECTION_MAP:
        return f"Error: Unknown collection '{collection}'. Valid: {', '.join(sorted(_COLLECTION_MAP))}"
    _agent_gate.observe(tool='delete_record', verb='delete', collection=collection, record_id=id)
    if collection == 'contracttemplate':
        return (
            "Error: Generic contract-template deletion is blocked. "
            "Use the authenticated CRM template-management workflow for any approved retirement."
        )
    if collection == 'servicelocation':
        return (
            "Error: Standalone service-location deletion is blocked. "
            "Use a contract update with replace_service_locations=true and the complete "
            "intended row list so removal is explicit and pricing is revalidated atomically."
        )

    model, _ = _COLLECTION_MAP[collection]

    try:
        instance = model.objects.get(id=id)
    except model.DoesNotExist:
        return f"Error: {collection} with ID '{id}' not found."

    name = getattr(instance, 'name', None) or getattr(instance, 'contract_number', None) or str(id)
    instance.delete()
    return f"Deleted {collection} '{name}' ({id})."


@mcp_server.tool()
def renewal_book(year: int, month: int, currency: str = "") -> str:
    """The Renewal Book — every contract whose term ends in a given month (the CRM equivalent of a
    renewal-funnel month tab). Use this to see what is up for renewal, its status, and whether it
    has been renewed/paid — instead of the Google Sheets.

    Each row: corporate_group, company, country, end_date, zones, value, currency, product
    (Soundtrack/Beat Breeze), lifecycle_type, status, cancelled flag, auto_renew, billing_frequency,
    successor_contract + successor_status (via the renewed-from link), invoices_paid, outstanding_amount.
    Plus footer totals_by_product (contracts/zones/value) and totals_by_status.

    Args:
        year: e.g. 2026
        month: 1-12
        currency: optional 'USD' or 'THB' to match one funnel sheet; omit to see both.

    Returns: JSON {year, month, month_label, currency, count, totals_by_product, totals_by_status, rows}.
    """
    from crm_app.services.renewal_book_service import build_renewal_book
    try:
        data = build_renewal_book(year, month, currency or None)
    except (TypeError, ValueError) as e:
        return f"Error: {e}. Provide year and month (1-12), e.g. year=2026, month=9."
    return _json.dumps(data)


@mcp_server.tool()
def convert_quote_to_contract(quote_id: str, overrides_json: str = "") -> str:
    """Turn an accepted quote into a Draft contract: copies the terms + line items, derives the
    service locations, and links the quote. Idempotent — if the quote already has a (non-cancelled)
    contract, that one is returned and nothing new is created.

    Args:
        quote_id: the quote's UUID.
        overrides_json: optional JSON object with any of start_date, end_date,
            contract_duration_months, billing_frequency, property_name, notes, price_per_zone,
            customer_contact_name, customer_contact_title, customer_contact_email,
            billing_entity, payment_schedule, payment_custom, preamble_custom,
            activation_custom, custom_terms. Quote terms_conditions copy verbatim to
            payment_custom; explicit payment_schedule and issuer are preserved.
            Unsupported fields return a clarification error, never silent success.

    Returns: JSON with contract_id, contract_number, status, and a message. NOTE: the derived
    service-location product/zone mapping is best-effort — read them back and correct if needed.
    """
    from crm_app.models import Quote
    from crm_app.services.quote_conversion import convert_quote_to_contract as _convert
    _agent_gate.observe(tool='convert_quote_to_contract', verb='convert_quote', collection='quote',
                        record_id=quote_id, data=overrides_json)
    try:
        quote = Quote.objects.get(id=quote_id)
    except Quote.DoesNotExist:
        return f"Error: quote '{quote_id}' not found."
    overrides = {}
    if overrides_json:
        try:
            overrides = _json.loads(overrides_json)
        except _json.JSONDecodeError as e:
            return f"Error: invalid overrides_json — {e}"
    try:
        contract, info = _convert(quote, overrides)
    except (TypeError, ValueError) as exc:
        return _json.dumps({'error': 'clarification_required', 'detail': str(exc)})
    return _json.dumps({'contract_id': str(contract.id), 'contract_number': contract.contract_number,
                        'status': contract.status, **info})

# ============================================================
# Custom tools — PDF generation
# ============================================================


def _pdf_response_payload(response, default_filename: str) -> str:
    """Shape a ViewSet PDF response into a JSON string with base64 content.

    Returns JSON with keys: filename, size, content_b64. Callers parse with
    json.loads and base64.b64decode(content_b64) to recover raw PDF bytes.
    """
    if response.status_code != 200:
        detail = getattr(response, 'data', None)
        if not isinstance(detail, dict):
            try:
                detail = json.loads(response.content)
            except (TypeError, ValueError, AttributeError):
                detail = None
        payload = dict(detail) if isinstance(detail, dict) else {}
        payload.setdefault('error', f'HTTP {response.status_code}')
        payload['status_code'] = response.status_code
        return json.dumps(payload, default=str)

    content_disp = response.get('Content-Disposition', '')
    filename = (
        content_disp.split('filename=')[-1].strip('"')
        if 'filename=' in content_disp
        else default_filename
    )
    return json.dumps({
        "filename": filename,
        "size": len(response.content),
        "content_b64": base64.b64encode(response.content).decode('ascii'),
    })


@mcp_server.tool()
def generate_contract_pdf(
    id: str, reserve_renewal_number: bool = False, expected_version: str = ""
) -> str:
    """Generate a contract PDF by contract ID.

    Returns JSON string: {"filename": str, "size": int, "content_b64": str}.
    Parse with json.loads, then base64.b64decode(content_b64) for raw bytes.
    On failure returns {"error": "..."}.

    Cira's renewal review option: reserve_renewal_number=True requires the exact
    current contract updated_at in expected_version and an existing linked Draft
    renewal. Reserve its final number before rendering without changing status,
    sent_date, activation, or its predecessor. Retrying a numbered Draft reuses
    its number. Inspect the returned PDF and obtain Nikki's approval before any
    delivery; never change the approved PDF after approval.
    """
    from django.test import RequestFactory
    from crm_app.models import Contract

    def render(contract):
        factory = RequestFactory()
        request = factory.get(f'/api/v1/contracts/{contract.id}/pdf/')
        request.user = _get_system_user()
        request._bmasia_suppress_pdf_activity = True
        viewset = ContractViewSet.as_view({'get': 'pdf'})
        return viewset(request, pk=contract.id)

    from django.core.exceptions import ValidationError
    from crm_app.services.contract_review import (
        ContractReviewError,
        generate_numbered_renewal_review,
    )

    if type(reserve_renewal_number) is not bool:
        return json.dumps({"error": "reserve_renewal_number must be a boolean."})
    if reserve_renewal_number:
        _agent_gate.observe(tool='generate_contract_pdf', verb='reserve_number', collection='contract',
                            record_id=id, expected_version=expected_version)
    try:
        if reserve_renewal_number:
            response, metadata = generate_numbered_renewal_review(id, expected_version, render)
            return json.dumps({**json.loads(_pdf_response_payload(response, f'contract_{id}.pdf')), **metadata})
        contract = Contract.objects.get(id=id)
        return _pdf_response_payload(render(contract), f'contract_{id}.pdf')
    except Contract.DoesNotExist:
        return json.dumps({"error": f"Contract with ID '{id}' not found."})
    except ContractReviewError as exc:
        return json.dumps({"error": str(exc)})
    except (ValidationError, ValueError):
        return json.dumps({"error": "Invalid contract ID or review version."})


@mcp_server.tool()
def generate_proforma_pdf(id: str) -> str:
    """Generate a PROFORMA INVOICE PDF for a contract by contract ID.

    Standalone advance-payment document for the renewal pack — clearly marked
    "not a tax invoice", creates NO Invoice record and touches no AR/tax data.
    The official tax invoice still issues on payment via the Invoice flow.

    Returns JSON string: {"filename": str, "size": int, "content_b64": str}.
    Parse with json.loads, then base64.b64decode(content_b64) for raw bytes.
    On failure returns {"error": "..."}.
    """
    from django.test import RequestFactory
    from crm_app.models import Contract

    try:
        Contract.objects.get(id=id)
    except Contract.DoesNotExist:
        return json.dumps({"error": f"Contract with ID '{id}' not found."})

    factory = RequestFactory()
    request = factory.get(f'/api/v1/contracts/{id}/proforma-pdf/')
    request.user = _get_system_user()

    viewset = ContractViewSet.as_view({'get': 'proforma_pdf'})
    response = viewset(request, pk=id)
    return _pdf_response_payload(response, f'proforma_{id}.pdf')


@mcp_server.tool()
def generate_quote_pdf(id: str) -> str:
    """Generate a quote PDF by quote ID.

    Returns JSON string: {"filename": str, "size": int, "content_b64": str}.
    Parse with json.loads, then base64.b64decode(content_b64) for raw bytes.
    On failure returns {"error": "..."}.
    """
    from django.test import RequestFactory
    from crm_app.models import Quote

    try:
        Quote.objects.get(id=id)
    except Quote.DoesNotExist:
        return json.dumps({"error": f"Quote with ID '{id}' not found."})

    factory = RequestFactory()
    request = factory.get(f'/api/v1/quotes/{id}/pdf/')
    request.user = _get_system_user()
    request._bmasia_suppress_pdf_activity = True

    viewset = QuoteViewSet.as_view({'get': 'pdf'})
    response = viewset(request, pk=id)
    return _pdf_response_payload(response, f'quote_{id}.pdf')


@mcp_server.tool()
def generate_invoice_pdf(id: str) -> str:
    """Generate an invoice PDF by invoice ID.

    Returns JSON string: {"filename": str, "size": int, "content_b64": str}.
    Parse with json.loads, then base64.b64decode(content_b64) for raw bytes.
    On failure returns {"error": "..."}.
    """
    from django.test import RequestFactory
    from crm_app.models import Invoice

    try:
        Invoice.objects.get(id=id)
    except Invoice.DoesNotExist:
        return json.dumps({"error": f"Invoice with ID '{id}' not found."})

    factory = RequestFactory()
    request = factory.get(f'/api/v1/invoices/{id}/pdf/')
    request.user = _get_system_user()
    request._bmasia_suppress_pdf_activity = True

    viewset = InvoiceViewSet.as_view({'get': 'pdf'})
    response = viewset(request, pk=id)
    return _pdf_response_payload(response, f'invoice_{id}.pdf')


def _get_system_user():
    """Get or create a system user for MCP tool operations."""
    from django.contrib.auth import get_user_model
    from types import SimpleNamespace

    User = get_user_model()
    try:
        return User.objects.filter(role='Admin').first() or User.objects.first()
    except Exception:
        # Return anonymous-like user for PDF generation
        return SimpleNamespace(is_authenticated=False, pk=None)


logger.info("BMAsia CRM MCP tools registered successfully.")
