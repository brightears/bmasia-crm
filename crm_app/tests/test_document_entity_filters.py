"""Accounting and renewal numbering use the document's selected issuer."""

from datetime import date
from decimal import Decimal

import pytest

from crm_app.models import Company, Contract, Invoice, Quote
from crm_app.services.document_entity_filters import filter_document_entity


pytestmark = pytest.mark.django_db
THAILAND = "BMAsia (Thailand) Co., Ltd."
HONG_KONG = "BMAsia Limited"


@pytest.fixture
def companies():
    return {
        "th": Company.objects.create(
            name="Thai-default Customer", billing_entity=THAILAND, country="Hong Kong",
        ),
        "hk": Company.objects.create(
            name="HK-default Customer", billing_entity=HONG_KONG, country="Thailand",
        ),
    }


def _document(model, company, suffix, override=""):
    common = {"company": company, "billing_entity": override, "currency": "USD"}
    if model is Contract:
        return Contract.objects.create(
            **common, contract_number=f"DRAFT-ENTITY-{suffix}", status="Draft",
            start_date=date(2026, 9, 1), end_date=date(2027, 8, 31),
            value=Decimal("260.00"), total_value=Decimal("260.00"),
        )
    if model is Quote:
        return Quote.objects.create(
            **common, quote_number=f"ENTITY-QT-{suffix}", status="Draft",
            valid_from=date(2026, 9, 1), valid_until=date(2026, 9, 30),
            subtotal=Decimal("260.00"), total_value=Decimal("260.00"),
        )
    return Invoice.objects.create(
        **common, invoice_number=f"ENTITY-IV-{suffix}", status="Draft",
        issue_date=date(2026, 9, 1), due_date=date(2026, 9, 30),
        amount=Decimal("260.00"), total_amount=Decimal("260.00"),
    )


@pytest.mark.parametrize("model", [Contract, Quote, Invoice])
@pytest.mark.parametrize("use_slug", [False, True])
def test_entity_filters_follow_override_then_company_without_overlap(companies, model, use_slug):
    th_default = _document(model, companies["th"], "TH-default")
    hk_default = _document(model, companies["hk"], "HK-default")
    th_override = _document(model, companies["hk"], "TH-override", THAILAND)
    hk_override = _document(model, companies["th"], "HK-override", HONG_KONG)

    th_filter = "bmasia_th" if use_slug else THAILAND
    hk_filter = "bmasia_hk" if use_slug else HONG_KONG
    assert set(filter_document_entity(model.objects.all(), th_filter).values_list("pk", flat=True)) == {
        th_default.pk, th_override.pk,
    }
    assert set(filter_document_entity(model.objects.all(), hk_filter).values_list("pk", flat=True)) == {
        hk_default.pk, hk_override.pk,
    }
    assert filter_document_entity(model.objects.all(), "all").count() == 4
    companies["th"].refresh_from_db()
    companies["hk"].refresh_from_db()
    assert companies["th"].billing_entity == THAILAND
    assert companies["hk"].billing_entity == HONG_KONG


def test_unknown_entity_filter_is_not_silently_an_hk_or_all_report():
    with pytest.raises(ValueError, match="Unsupported billing entity filter"):
        filter_document_entity(Invoice.objects.all(), "Unverified Supplier")


def test_related_document_filter_supports_explicit_prefix(companies):
    contract = _document(Contract, companies["hk"], "prefix", THAILAND)
    invoice = _document(Invoice, companies["hk"], "prefix")
    Invoice.objects.filter(pk=invoice.pk).update(contract=contract)
    assert list(filter_document_entity(
        Invoice.objects.all(), "bmasia_th", prefix="contract__",
    ).values_list("pk", flat=True)) == [invoice.pk]


def test_standalone_invoice_appears_in_correct_ar_and_balance_sheet(companies):
    from crm_app.services.ar_aging_service import ARAgingService
    from crm_app.services.balance_sheet_service import BalanceSheetService

    invoice = _document(Invoice, companies["hk"], "standalone-ar", THAILAND)
    Invoice.objects.filter(pk=invoice.pk).update(status="Sent")
    ar = ARAgingService().get_outstanding_invoices(
        as_of_date=date(2026, 9, 30), currency="USD", billing_entity="bmasia_th",
    )
    assert list(ar.values_list("pk", flat=True)) == [invoice.pk]
    assert not ARAgingService().get_outstanding_invoices(billing_entity="bmasia_hk").exists()
    amount, detail = BalanceSheetService()._get_accounts_receivable(
        2026, 3, "bmasia_th", "USD", None,
    )
    assert amount == Decimal("260.00")
    assert detail["sent"]["count"] == 1


def test_standalone_paid_invoice_cash_follows_issuer_not_customer(companies):
    from crm_app.services.cash_flow_service import CashFlowService

    invoice = _document(Invoice, companies["hk"], "standalone-cash", THAILAND)
    Invoice.objects.filter(pk=invoice.pk).update(status="Paid", paid_date=date(2026, 9, 9))
    assert CashFlowService()._get_cash_from_customers(
        2026, 9, "bmasia_th", "USD", None,
    ) == (Decimal("260.00"), 1)
    assert CashFlowService()._get_cash_from_customers(
        2026, 9, "bmasia_hk", "USD", None,
    ) == (Decimal("0"), 0)


def test_profit_loss_contract_revenue_follows_document_override(companies):
    from crm_app.services.profit_loss_service import ProfitLossService

    contract = _document(Contract, companies["hk"], "pl", THAILAND)
    Contract.objects.filter(pk=contract.pk).update(
        lifecycle_type="new", lifecycle_effective_date=date(2026, 9, 1),
    )
    service = ProfitLossService()
    assert service._calculate_revenue_from_contracts(2026, 9, "bmasia_th", "USD")["new_value"] == Decimal("260.00")
    assert service._calculate_revenue_from_contracts(2026, 9, "bmasia_hk", "USD")["new_value"] == Decimal("0")


def test_revenue_schedule_follows_invoice_override_not_linked_contract(companies):
    from crm_app.services.revenue_recognition_service import RevenueRecognitionService

    contract = _document(Contract, companies["hk"], "recognition")
    invoice = _document(Invoice, companies["hk"], "recognition", THAILAND)
    Invoice.objects.filter(pk=invoice.pk).update(contract=contract)
    invoice.refresh_from_db()
    invoice.line_items.create(
        product_service="Beat Breeze", description="Annual Lobby service",
        quantity=Decimal("1.00"), unit_price=Decimal("260.00"),
        tax_rate=Decimal("0.00"),
        service_period_start=date(2026, 9, 1), service_period_end=date(2027, 8, 31),
    )
    schedules = RevenueRecognitionService().generate_schedule_from_invoice(invoice)
    assert len(schedules) == 1
    assert schedules[0].billing_entity == "bmasia_th"
    assert schedules[0].currency == "USD"
    assert schedules[0].amount == Decimal("260.00")


def test_renewal_review_number_uses_override_without_changing_contract(companies):
    from crm_app.services.rene_phase2 import _reserve_final_contract_number

    contract = _document(Contract, companies["hk"], "renewal", THAILAND)
    before = Contract.objects.values().get(pk=contract.pk)
    assert _reserve_final_contract_number(contract).startswith("TH-CT")
    assert Contract.objects.values().get(pk=contract.pk) == before
