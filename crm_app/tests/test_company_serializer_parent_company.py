from crm_app.serializers import CompanySerializer


def test_company_serializer_accepts_empty_optional_parent_company_value():
    serializer = CompanySerializer(data={'parent_company': ''}, partial=True)

    assert serializer.is_valid(), serializer.errors


def test_company_serializer_accepts_null_optional_parent_company_value():
    serializer = CompanySerializer(data={'parent_company': None}, partial=True)

    assert serializer.is_valid(), serializer.errors
