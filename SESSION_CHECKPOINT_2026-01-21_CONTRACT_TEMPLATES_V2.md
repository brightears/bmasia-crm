# Session Checkpoint: Contract Templates - Full Template Approach
**Date**: January 21, 2026
**Status**: In Progress - Discussing Simplification

---

## CRITICAL CONTEXT FOR NEXT SESSION

### The Key Insight

The user realized that templates can contain the **ENTIRE contract structure** (not just preamble snippets). This means:

1. **Current complex system** has 3 hardcoded PDF generators in Python:
   - `_generate_principal_terms_pdf()` - complex numbered clauses, zone tables
   - `_generate_master_agreement_pdf()` - corporate governance structure
   - `_generate_participation_agreement_pdf()` - references master contract

2. **User's simpler approach**: Put ALL contract content in the template with HTML formatting:
   - Template = entire contract text with `<b>`, `<br/>`, etc.
   - Variables like `{{company_name}}`, `{{client_address}}` get substituted
   - ONE simple PDF generator that renders the template content
   - NO need for Contract Category dropdown

### Example Full Template (User Created)

```html
<b>PRINCIPAL TERMS</b><br/><br/>

This agreement is made the {{agreement_date}} between:<br/><br/>

<b>BMAsia (Thailand) Company Limited</b>, with registered address at 725 S-Metro Building, Suite 144, Level 20, Sukhumvit Road, Klongtan Nuea, Watthana, Bangkok 10110 Thailand (<b>BMA</b>)<br/><br/>

and<br/><br/>

<b>{{legal_entity_name}}</b>, with registered address at {{client_address}} (<b>Client</b>) (together "the Parties")<br/><br/>

[... full contract text with all clauses, signature blocks, etc. ...]
```

### The Proposed Simplification

**Remove:**
- Contract Category dropdown from ContractForm
- Multiple PDF generator functions (or at least simplify to one)
- Complex hardcoded PDF structure in Python

**Keep:**
- Contract Template selection (which contains FULL contract)
- Variable substitution (`{{company_name}}`, etc.)
- Simple PDF rendering of template content

**Result:**
- User creates different templates for: Standard, Corporate Master, Participation, Hilton HPA
- Each template has its complete structure built in
- System just renders the template content as PDF
- Much simpler architecture

---

## Today's Completed Work

### Contract Templates Management Page
- Created `/contract-templates` page with full CRUD
- ContractTemplateForm with variable guide (click to copy, double-click to insert)
- Search, filter by status, pagination
- Simplified form: removed Template Type dropdown, removed Default switch

### Backend Template Variables Added
All these variables now work in templates:
- `{{company_name}}`, `{{legal_entity_name}}`, `{{client_address}}`
- `{{contact_name}}`, `{{contact_email}}`
- `{{contract_number}}`, `{{start_date}}`, `{{end_date}}`, `{{agreement_date}}`
- `{{value}}`, `{{currency}}`, `{{billing_frequency}}`, `{{payment_terms}}`
- `{{venue_names}}`, `{{number_of_zones}}`
- `{{client_signatory_name}}`, `{{client_signatory_title}}`

### Git Commits Today
```
7a15eb70 Simplify Contract Template form and list
cd01e7c1 Add more template variables to backend substitution
624e8f08 Add more template variables for contract templates
520cc6d8 Docs: Update documentation and create session checkpoint
f6eb95de Add Contract Templates management page
8872a13c Add contract template dropdown to ContractForm
```

---

## Next Steps (When Resuming)

1. **Discuss with user**: Confirm the "full template" approach is what they want
2. **If yes, implement**:
   - Modify PDF generator to just render template content (simple paragraph-based PDF)
   - Remove Contract Category dropdown from ContractForm
   - Keep template selection as the only choice
   - Handle zones table separately (or add a `{{zones_table}}` special variable?)

3. **Open question**: Should the zones table be:
   - A) Included in the template text (user writes it manually)
   - B) Auto-generated and inserted via a special `{{zones_table}}` variable
   - C) Always appended after template content

---

## Files Modified Today

| File | Status |
|------|--------|
| `crm_app/views.py` | Added template variables to `_substitute_template_variables()` |
| `ContractTemplateForm.tsx` | Simplified (removed Type, Default) |
| `ContractTemplates.tsx` | Simplified (removed Type filter/column) |
| `ContractForm.tsx` | Added template dropdown |
| `api.ts` | Added create/update/delete template methods |

---

## Production URLs

- Frontend: https://bmasia-crm-frontend.onrender.com
- Backend: https://bmasia-crm.onrender.com
- Contract Templates: https://bmasia-crm-frontend.onrender.com/contract-templates
