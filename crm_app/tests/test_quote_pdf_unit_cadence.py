from types import SimpleNamespace

from crm_app.quote_pdf_v2 import subscription_unit_suffix


def _quote(billing_frequency, duration_months):
    return SimpleNamespace(billing_frequency=billing_frequency, contract_duration_months=duration_months)


def test_prorated_one_time_addon_is_priced_per_period():
    # TH-QT26121: two zones prorated to an existing contract, 3 months, one-time.
    assert subscription_unit_suffix(_quote("one-time", 3)) == "per zone / period"


def test_sub_annual_term_is_priced_per_period():
    assert subscription_unit_suffix(_quote("annual", 6)) == "per zone / period"


def test_one_time_full_year_is_priced_per_period():
    assert subscription_unit_suffix(_quote("one-time", 12)) == "per zone / period"


def test_annual_and_multi_year_terms_keep_per_year():
    assert subscription_unit_suffix(_quote("annual", 12)) == "per zone / year"
    assert subscription_unit_suffix(_quote("upfront", 24)) == "per zone / year"
    assert subscription_unit_suffix(_quote(None, None)) == "per zone / year"
