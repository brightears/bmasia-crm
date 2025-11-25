# Quick Test Guide - Contract-Zone Integration

## Run All Tests
```bash
cd "/Users/benorbe/Library/Mobile Documents/com~apple~CloudDocs/Documents/Coding Projects/BMAsia CRM"
env/bin/pytest crm_app/tests/test_contract_zone_*.py -v
```

## Run by Category

### Model Tests (24 tests)
```bash
env/bin/pytest crm_app/tests/test_contract_zone_models.py -v
```

### Signal Tests (11 tests)
```bash
env/bin/pytest crm_app/tests/test_contract_zone_signals.py -v
```

### Serializer Tests (20 tests)
```bash
env/bin/pytest crm_app/tests/test_contract_zone_serializers.py -v
```

### API Tests (29 tests)
```bash
env/bin/pytest crm_app/tests/test_contract_zone_api.py -v
```

### Admin Tests (15 tests)
```bash
env/bin/pytest crm_app/tests/test_contract_zone_admin.py -v
```

## Coverage Report
```bash
env/bin/pytest crm_app/tests/test_contract_zone_*.py \
  --cov=crm_app.models \
  --cov=crm_app.signals \
  --cov=crm_app.serializers \
  --cov=crm_app.views \
  --cov-report=html
```

Then open `htmlcov/index.html` in your browser.

## Test Counts
- **Total**: 99 tests
- **Models**: 24 tests
- **Signals**: 11 tests
- **Serializers**: 20 tests
- **API**: 29 tests
- **Admin**: 15 tests

## Expected Results
- All 99 tests should pass
- Execution time: ~60 seconds
- Coverage: 91% on signals, 70% on models

See `CONTRACT_ZONE_TEST_REPORT.md` for detailed report.
