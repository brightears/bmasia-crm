"""
MCP Server tools for BMAsia CRM.

Exposes core CRM ViewSets as MCP tools via django-mcp-server.
Endpoint: /mcp/ with Token authentication.
"""
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
quote, opportunity, task, zone, clienttechdetail, device, ticket, kbarticle.

### CRUD Tools (write)
Use these 3 generic tools for all write operations:
- `create_record(collection, data)` — create a new record (data is a JSON string)
- `update_record(collection, id, data)` — partial update (only include changed fields)
- `delete_record(collection, id)` — delete a record

Supported collections: company, contact, contract, invoice, quote, opportunity,
task, zone, clienttechdetail, device, ticket, kbarticle.

### PDF Tools
- `generate_contract_pdf(id)` — generate contract PDF
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
        'full_address', 'status', 'notes', 'parent_company',
        'created_at', 'updated_at',
    ]
    search_fields = ['name', 'legal_entity_name', 'email', 'city', 'country', 'notes']
    extra_instructions = "Use this to look up hotels, resorts, and corporate clients."


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
        'id', 'contract_number', 'company', 'contract_type', 'status',
        'start_date', 'end_date', 'value', 'currency', 'monthly_value',
        'total_value', 'billing_frequency', 'payment_terms', 'notes',
        'master_contract', 'created_at', 'updated_at',
    ]
    search_fields = ['contract_number', 'notes', 'payment_terms']
    extra_instructions = (
        "Status lifecycle: Draft → Sent → Active → Renewed/Expired/Cancelled. "
        "Use $lookup with 'company' to join company details."
    )


class InvoiceQuery(ModelQueryToolset):
    model = Invoice
    fields = [
        'id', 'invoice_number', 'company', 'contract', 'status',
        'invoice_date', 'due_date', 'paid_date', 'subtotal', 'total_tax',
        'total_amount', 'currency', 'notes', 'created_at',
    ]
    search_fields = ['invoice_number', 'notes']
    extra_instructions = "Status: Draft, Sent, Paid, Overdue, Void, Cancelled."


class QuoteQuery(ModelQueryToolset):
    model = Quote
    fields = [
        'id', 'quote_number', 'company', 'status', 'quote_date',
        'valid_until', 'subtotal', 'total_value', 'currency',
        'notes', 'created_at',
    ]
    search_fields = ['quote_number', 'notes']


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
}


def _get_serializer_class(dotted_path):
    """Import and return a serializer class from its dotted path."""
    from importlib import import_module
    module_path, class_name = dotted_path.rsplit('.', 1)
    module = import_module(module_path)
    return getattr(module, class_name)


@mcp_server.tool()
def create_record(collection: str, data: str) -> str:
    """Create a new record in a CRM collection.

    Args:
        collection: Collection name (company, contact, contract, invoice, quote,
                    opportunity, task, zone, clienttechdetail, device, ticket, kbarticle)
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

    instance = serializer.save()
    return f"Updated {collection} {id} successfully."


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

# ============================================================
# Custom tools — PDF generation
# ============================================================


@mcp_server.tool()
def generate_contract_pdf(id: str) -> str:
    """Generate a contract PDF by contract ID. Returns the PDF filename and size."""
    from django.test import RequestFactory
    from crm_app.models import Contract

    try:
        contract = Contract.objects.get(id=id)
    except Contract.DoesNotExist:
        return f"Error: Contract with ID '{id}' not found."

    factory = RequestFactory()
    request = factory.get(f'/api/v1/contracts/{id}/pdf/')
    request.user = _get_system_user()

    viewset = ContractViewSet.as_view({'get': 'pdf'})
    response = viewset(request, pk=id)

    if response.status_code == 200:
        content_disp = response.get('Content-Disposition', '')
        filename = content_disp.split('filename=')[-1].strip('"') if 'filename=' in content_disp else f'contract_{id}.pdf'
        return f"PDF generated: {filename} ({len(response.content):,} bytes)"
    else:
        return f"Error generating PDF: HTTP {response.status_code}"


@mcp_server.tool()
def generate_quote_pdf(id: str) -> str:
    """Generate a quote PDF by quote ID. Returns the PDF filename and size."""
    from django.test import RequestFactory
    from crm_app.models import Quote

    try:
        quote = Quote.objects.get(id=id)
    except Quote.DoesNotExist:
        return f"Error: Quote with ID '{id}' not found."

    factory = RequestFactory()
    request = factory.get(f'/api/v1/quotes/{id}/pdf/')
    request.user = _get_system_user()

    viewset = QuoteViewSet.as_view({'get': 'pdf'})
    response = viewset(request, pk=id)

    if response.status_code == 200:
        content_disp = response.get('Content-Disposition', '')
        filename = content_disp.split('filename=')[-1].strip('"') if 'filename=' in content_disp else f'quote_{id}.pdf'
        return f"PDF generated: {filename} ({len(response.content):,} bytes)"
    else:
        return f"Error generating PDF: HTTP {response.status_code}"


@mcp_server.tool()
def generate_invoice_pdf(id: str) -> str:
    """Generate an invoice PDF by invoice ID. Returns the PDF filename and size."""
    from django.test import RequestFactory
    from crm_app.models import Invoice

    try:
        invoice = Invoice.objects.get(id=id)
    except Invoice.DoesNotExist:
        return f"Error: Invoice with ID '{id}' not found."

    factory = RequestFactory()
    request = factory.get(f'/api/v1/invoices/{id}/pdf/')
    request.user = _get_system_user()

    viewset = InvoiceViewSet.as_view({'get': 'pdf'})
    response = viewset(request, pk=id)

    if response.status_code == 200:
        content_disp = response.get('Content-Disposition', '')
        filename = content_disp.split('filename=')[-1].strip('"') if 'filename=' in content_disp else f'invoice_{id}.pdf'
        return f"PDF generated: {filename} ({len(response.content):,} bytes)"
    else:
        return f"Error generating PDF: HTTP {response.status_code}"


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
