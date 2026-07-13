"""
MCP Server tools for BMAsia CRM.

Exposes core CRM ViewSets as MCP tools via django-mcp-server.
Endpoint: /mcp/ with Token authentication.
"""
import base64
import json
import logging

from mcp_server import mcp_server
from mcp_server.query_tool import ModelQueryToolset

from crm_app.models import (
    Company, Contact, Contract, Invoice, Quote, Opportunity,
    Task, Zone, ContractLineItem, InvoiceLineItem, QuoteLineItem,
    ContractServiceLocation, ClientTechDetail, Device, Ticket, KBArticle,
)
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
quotelineitem, contractlineitem, invoicelineitem.

### CRUD Tools (write)
Use these 3 generic tools for all write operations:
- `create_record(collection, data)` — create a new record (data is a JSON string)
- `update_record(collection, id, data)` — partial update (only include changed fields)
- `delete_record(collection, id)` — delete a record

Supported collections: company, contact, contract, invoice, quote, opportunity,
task, zone, clienttechdetail, device, ticket, kbarticle, quotelineitem,
contractlineitem, invoicelineitem.

### PDF Tools
Each returns a JSON string with `filename`, `size`, and `content_b64` (base64-
encoded PDF bytes). Parse with `json.loads`, then `base64.b64decode(content_b64)`
to recover the raw PDF. On failure returns `{"error": "..."}`.
- `generate_contract_pdf(id)` — generate contract PDF
- `generate_proforma_pdf(id)` — generate PROFORMA INVOICE PDF from a contract (advance-payment
  request for the renewal pack; marked "not a tax invoice"; creates no Invoice/AR/tax record)
- `generate_quote_pdf(id)` — generate quote PDF
- `generate_invoice_pdf(id)` — generate invoice PDF

## Key Concepts
- **billing_entity**: 'BMAsia (Thailand) Co., Ltd.' (THB) or 'BMAsia Limited' (USD)
- **Contract status**: Draft → Sent → Active → Renewed/Expired/Cancelled
- **Invoice status**: Draft → Sent → Paid/Overdue/Void
- **Quote status**: Draft → Sent → Accepted/Rejected/Expired
- **Service locations** on contracts are separate from line items — they control
  what appears in the PDF "Locations for Provision of Services" table.
- Contract numbers are auto-generated (read-only).
""")

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
        'is_primary', 'title', 'notes', 'created_at',
    ]
    search_fields = ['name', 'email', 'phone', 'title', 'notes']
    extra_instructions = "Contacts belong to companies. contact_type: Primary, Billing, Technical, Decision Maker, Other."


class ContractQuery(ModelQueryToolset):
    model = Contract
    fields = [
        'id', 'contract_number', 'company', 'contract_type', 'service_type', 'status',
        'lifecycle_type', 'start_date', 'end_date', 'value', 'currency',
        'total_value', 'billing_frequency', 'payment_terms', 'auto_renew',
        'renewal_period_months', 'renewed_from', 'renewal_notice_sent', 'sent_date',
        'contract_category', 'is_active', 'master_contract', 'notes',
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


class InvoiceQuery(ModelQueryToolset):
    model = Invoice
    fields = [
        'id', 'invoice_number', 'company', 'contract', 'status',
        'invoice_date', 'due_date', 'paid_date', 'amount', 'tax_amount',
        'total_amount', 'currency', 'notes', 'created_at',
    ]
    search_fields = ['invoice_number', 'notes']
    extra_instructions = "Status: Draft, Sent, Paid, Overdue, Void, Cancelled."


class QuoteQuery(ModelQueryToolset):
    model = Quote
    fields = [
        'id', 'quote_number', 'company', 'opportunity', 'status', 'quote_type',
        'valid_from', 'valid_until', 'subtotal', 'total_value', 'currency',
        'billing_frequency', 'contract_duration_months', 'notes', 'created_at',
    ]
    search_fields = ['quote_number', 'notes']
    extra_instructions = ("Use convert_quote_to_contract to turn an accepted quote into a Draft contract "
                          "(copies terms + line items, derives service locations).")


class OpportunityQuery(ModelQueryToolset):
    model = Opportunity
    fields = [
        'id', 'name', 'company', 'contact', 'stage', 'value', 'currency',
        'probability', 'expected_close_date', 'lead_source', 'contact_method',
        'notes', 'created_at',
    ]
    search_fields = ['name', 'notes']
    extra_instructions = "Stages: Lead, Qualified, Proposal, Negotiation, Closed Won, Closed Lost."


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
        'is_active', 'platform_type', 'created_at',
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


@mcp_server.tool()
def create_record(collection: str, data: str) -> str:
    """Create a new record in a CRM collection.

    Args:
        collection: Collection name (company, contact, contract, invoice, quote,
                    opportunity, task, zone, clienttechdetail, device, ticket, kbarticle,
                    quotelineitem, contractlineitem, invoicelineitem)
        data: JSON string with field values. Use query_data_collections to check
              field names and valid choices first.

    Returns: JSON with the created record's id and key fields, or validation errors.
    """
    if collection not in _COLLECTION_MAP:
        return f"Error: Unknown collection '{collection}'. Valid: {', '.join(sorted(_COLLECTION_MAP))}"

    try:
        fields = _json.loads(data)
    except _json.JSONDecodeError as e:
        return f"Error: Invalid JSON — {e}"

    model, serializer_path = _COLLECTION_MAP[collection]
    SerializerClass = _get_serializer_class(serializer_path)

    serializer = SerializerClass(data=fields)
    if not serializer.is_valid():
        return f"Validation errors: {_json.dumps(serializer.errors)}"

    instance = serializer.save()
    # Return a concise summary
    result = {'id': str(instance.id)}
    for attr in ['name', 'contract_number', 'invoice_number', 'quote_number',
                 'ticket_number', 'article_number', 'title', 'email', 'subject']:
        if hasattr(instance, attr) and getattr(instance, attr):
            result[attr] = str(getattr(instance, attr))
    _, dropped = _dropped_keys(serializer, fields)
    if dropped:
        result['warning_ignored_keys'] = dropped
        result['warning'] = ('These keys were NOT saved (DRF drops non-writable keys silently). '
                             'Fix the key names and re-send if you intended to set them.')
    return _json.dumps(result)


@mcp_server.tool()
def update_record(collection: str, id: str, data: str) -> str:
    """Update an existing record in a CRM collection.

    Args:
        collection: Collection name (same options as create_record)
        id: UUID of the record to update
        data: JSON string with fields to update (partial update — only include
              fields you want to change)

    Returns: JSON with updated fields, or validation errors.
    """
    if collection not in _COLLECTION_MAP:
        return f"Error: Unknown collection '{collection}'. Valid: {', '.join(sorted(_COLLECTION_MAP))}"

    try:
        fields = _json.loads(data)
    except _json.JSONDecodeError as e:
        return f"Error: Invalid JSON — {e}"

    model, serializer_path = _COLLECTION_MAP[collection]

    try:
        instance = model.objects.get(id=id)
    except model.DoesNotExist:
        return f"Error: {collection} with ID '{id}' not found."

    SerializerClass = _get_serializer_class(serializer_path)
    serializer = SerializerClass(instance, data=fields, partial=True)
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
        src = serializer.fields[key].source or key
        val = getattr(instance, src, None)
        persisted[key] = str(val) if val is not None else None
    result = {'updated': True, 'id': str(id), 'applied': persisted}
    if dropped:
        result['warning_ignored_keys'] = dropped
        result['warning'] = ('These keys were NOT saved (DRF drops non-writable keys silently). '
                             'Fix the key names and re-send if you intended to set them.')
    return _json.dumps(result)


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
            customer_contact_name, customer_contact_title, customer_contact_email.

    Returns: JSON with contract_id, contract_number, status, and a message. NOTE: the derived
    service-location product/zone mapping is best-effort — read them back and correct if needed.
    """
    from crm_app.models import Quote
    from crm_app.services.quote_conversion import convert_quote_to_contract as _convert
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
    contract, info = _convert(quote, overrides)
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
        return json.dumps({"error": f"HTTP {response.status_code}"})

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
def generate_contract_pdf(id: str) -> str:
    """Generate a contract PDF by contract ID.

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
    request = factory.get(f'/api/v1/contracts/{id}/pdf/')
    request.user = _get_system_user()

    viewset = ContractViewSet.as_view({'get': 'pdf'})
    response = viewset(request, pk=id)
    return _pdf_response_payload(response, f'contract_{id}.pdf')


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
