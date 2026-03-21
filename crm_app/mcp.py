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
from crm_app.views import (
    CompanyViewSet, ContactViewSet, ContractViewSet, InvoiceViewSet,
    QuoteViewSet, OpportunityViewSet, TaskViewSet, ZoneViewSet,
    ClientTechDetailViewSet, DeviceViewSet, TicketViewSet, KBArticleViewSet,
)

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
**Sales:**
- Companies: list, create, update, delete
- Contacts: list, create, update, delete
- Contracts: list, create, update, delete
- Invoices: list, create, update, delete
- Quotes: list, create, update, delete
- Opportunities: list, create, update, delete
- Tasks: list, create, update, delete
- Zones: list

**Tech Support:**
- Client Tech Details: list, create, update, delete (hardware configs per outlet)
- Devices: list, create, update, delete (PCs, tablets, players)
- Tickets: list, create, update
- Knowledge Base: list, create, update

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
# DRF ViewSet tools (CRUD operations)
# ============================================================

# --- Companies ---
mcp_server.register_drf_list_tool(
    CompanyViewSet,
    name="list_companies",
    instructions="List companies with pagination. Returns paginated results.",
    actions={'get': 'list'},
)
mcp_server.register_drf_create_tool(
    CompanyViewSet,
    name="create_company",
    instructions="Create a new company. Required: name. Optional: billing_entity, industry, phone, email, country, city, address, etc.",
    actions={'post': 'create'},
)
mcp_server.register_drf_update_tool(
    CompanyViewSet,
    name="update_company",
    instructions="Update a company by ID. Pass only the fields to change.",
    actions={'patch': 'partial_update'},
)
mcp_server.register_drf_destroy_tool(
    CompanyViewSet,
    name="delete_company",
    instructions="Delete a company by ID.",
    actions={'delete': 'destroy'},
)

# --- Contacts ---
mcp_server.register_drf_list_tool(
    ContactViewSet,
    name="list_contacts",
    instructions="List contacts with pagination.",
    actions={'get': 'list'},
)
mcp_server.register_drf_create_tool(
    ContactViewSet,
    name="create_contact",
    instructions="Create a new contact. Required: name, company (ID). Optional: email, phone, contact_type, title.",
    actions={'post': 'create'},
)
mcp_server.register_drf_update_tool(
    ContactViewSet,
    name="update_contact",
    instructions="Update a contact by ID.",
    actions={'patch': 'partial_update'},
)
mcp_server.register_drf_destroy_tool(
    ContactViewSet,
    name="delete_contact",
    instructions="Delete a contact by ID.",
    actions={'delete': 'destroy'},
)

# --- Contracts ---
mcp_server.register_drf_list_tool(
    ContractViewSet,
    name="list_contracts",
    instructions="List contracts with pagination.",
    actions={'get': 'list'},
)
mcp_server.register_drf_create_tool(
    ContractViewSet,
    name="create_contract",
    instructions=(
        "Create a new contract. Required: company (ID), contract_type, status, start_date, end_date, "
        "value, currency, total_value. Include service_locations array for zones to appear in PDF. "
        "Contract number is auto-generated."
    ),
    actions={'post': 'create'},
)
mcp_server.register_drf_update_tool(
    ContractViewSet,
    name="update_contract",
    instructions="Update a contract by ID. Use PATCH (partial update) — do NOT send all fields.",
    actions={'patch': 'partial_update'},
)
mcp_server.register_drf_destroy_tool(
    ContractViewSet,
    name="delete_contract",
    instructions="Delete a contract by ID.",
    actions={'delete': 'destroy'},
)

# --- Invoices ---
mcp_server.register_drf_list_tool(
    InvoiceViewSet,
    name="list_invoices",
    instructions="List invoices with pagination.",
    actions={'get': 'list'},
)
mcp_server.register_drf_create_tool(
    InvoiceViewSet,
    name="create_invoice",
    instructions="Create a new invoice. Required: company (ID), invoice_date, due_date, currency. Include line_items array.",
    actions={'post': 'create'},
)
mcp_server.register_drf_update_tool(
    InvoiceViewSet,
    name="update_invoice",
    instructions="Update an invoice by ID.",
    actions={'patch': 'partial_update'},
)
mcp_server.register_drf_destroy_tool(
    InvoiceViewSet,
    name="delete_invoice",
    instructions="Delete an invoice by ID.",
    actions={'delete': 'destroy'},
)

# --- Quotes ---
mcp_server.register_drf_list_tool(
    QuoteViewSet,
    name="list_quotes",
    instructions="List quotes with pagination.",
    actions={'get': 'list'},
)
mcp_server.register_drf_create_tool(
    QuoteViewSet,
    name="create_quote",
    instructions="Create a new quote. Required: company (ID), quote_date, valid_until, currency. Include line_items array.",
    actions={'post': 'create'},
)
mcp_server.register_drf_update_tool(
    QuoteViewSet,
    name="update_quote",
    instructions="Update a quote by ID.",
    actions={'patch': 'partial_update'},
)
mcp_server.register_drf_destroy_tool(
    QuoteViewSet,
    name="delete_quote",
    instructions="Delete a quote by ID.",
    actions={'delete': 'destroy'},
)

# --- Opportunities ---
mcp_server.register_drf_list_tool(
    OpportunityViewSet,
    name="list_opportunities",
    instructions="List opportunities with pagination.",
    actions={'get': 'list'},
)
mcp_server.register_drf_create_tool(
    OpportunityViewSet,
    name="create_opportunity",
    instructions="Create a new opportunity. Required: name, company (ID), stage, value, currency.",
    actions={'post': 'create'},
)
mcp_server.register_drf_update_tool(
    OpportunityViewSet,
    name="update_opportunity",
    instructions="Update an opportunity by ID.",
    actions={'patch': 'partial_update'},
)
mcp_server.register_drf_destroy_tool(
    OpportunityViewSet,
    name="delete_opportunity",
    instructions="Delete an opportunity by ID.",
    actions={'delete': 'destroy'},
)

# --- Tasks ---
mcp_server.register_drf_list_tool(
    TaskViewSet,
    name="list_tasks",
    instructions="List tasks with pagination.",
    actions={'get': 'list'},
)
mcp_server.register_drf_create_tool(
    TaskViewSet,
    name="create_task",
    instructions="Create a new task. Required: title. Optional: description, status, priority, due_date, assigned_to (user ID), company (ID).",
    actions={'post': 'create'},
)
mcp_server.register_drf_update_tool(
    TaskViewSet,
    name="update_task",
    instructions="Update a task by ID.",
    actions={'patch': 'partial_update'},
)
mcp_server.register_drf_destroy_tool(
    TaskViewSet,
    name="delete_task",
    instructions="Delete a task by ID.",
    actions={'delete': 'destroy'},
)

# --- Zones (read-only for MCP) ---
mcp_server.register_drf_list_tool(
    ZoneViewSet,
    name="list_zones",
    instructions="List zones (music playback areas) with pagination.",
    actions={'get': 'list'},
)

# --- Client Tech Details ---
mcp_server.register_drf_list_tool(
    ClientTechDetailViewSet,
    name="list_client_tech_details",
    instructions="List client tech details (hardware configs per outlet). Filter by company, platform_type, outlet_name.",
    actions={'get': 'list'},
)
mcp_server.register_drf_create_tool(
    ClientTechDetailViewSet,
    name="create_client_tech_detail",
    instructions=(
        "Create a client tech detail record. Required: company (ID), outlet_name. "
        "Optional: platform_type, anydesk_id, ultraviewer_id, system_type, pc_name, operating_system, ram, etc."
    ),
    actions={'post': 'create'},
)
mcp_server.register_drf_update_tool(
    ClientTechDetailViewSet,
    name="update_client_tech_detail",
    instructions="Update a client tech detail by ID. Use to update AnyDesk IDs, hardware specs, etc.",
    actions={'patch': 'partial_update'},
)
mcp_server.register_drf_destroy_tool(
    ClientTechDetailViewSet,
    name="delete_client_tech_detail",
    instructions="Delete a client tech detail by ID.",
    actions={'delete': 'destroy'},
)

# --- Devices ---
mcp_server.register_drf_list_tool(
    DeviceViewSet,
    name="list_devices",
    instructions="List devices (PCs, tablets, players) with pagination.",
    actions={'get': 'list'},
)
mcp_server.register_drf_create_tool(
    DeviceViewSet,
    name="create_device",
    instructions="Create a device. Required: company (ID), name. Optional: device_type (pc/tablet/music_player/other), model_info, notes.",
    actions={'post': 'create'},
)
mcp_server.register_drf_update_tool(
    DeviceViewSet,
    name="update_device",
    instructions="Update a device by ID.",
    actions={'patch': 'partial_update'},
)
mcp_server.register_drf_destroy_tool(
    DeviceViewSet,
    name="delete_device",
    instructions="Delete a device by ID.",
    actions={'delete': 'destroy'},
)

# --- Tickets ---
mcp_server.register_drf_list_tool(
    TicketViewSet,
    name="list_tickets",
    instructions="List support tickets with pagination. Filter by status, priority, category.",
    actions={'get': 'list'},
)
mcp_server.register_drf_create_tool(
    TicketViewSet,
    name="create_ticket",
    instructions="Create a support ticket. Required: subject, description. Optional: priority, category, company (ID), contact (ID).",
    actions={'post': 'create'},
)
mcp_server.register_drf_update_tool(
    TicketViewSet,
    name="update_ticket",
    instructions="Update a ticket by ID. Use to change status, priority, assign to user, etc.",
    actions={'patch': 'partial_update'},
)

# --- Knowledge Base ---
mcp_server.register_drf_list_tool(
    KBArticleViewSet,
    name="list_kb_articles",
    instructions="List knowledge base articles. Filter by status, category, visibility.",
    actions={'get': 'list'},
)
mcp_server.register_drf_create_tool(
    KBArticleViewSet,
    name="create_kb_article",
    instructions="Create a knowledge base article. Required: title, content, category_id. Optional: visibility (public/internal), status (draft/published).",
    actions={'post': 'create'},
    body_schema={"type": "object", "description": "KB article data: title (str), content (str), category_id (uuid), visibility (public/internal), status (draft/published)"},
)
mcp_server.register_drf_update_tool(
    KBArticleViewSet,
    name="update_kb_article",
    instructions="Update a KB article by ID.",
    actions={'patch': 'partial_update'},
    body_schema={"type": "object", "description": "Fields to update: title, content, category_id, visibility, status"},
)

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
