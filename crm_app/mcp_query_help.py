"""Clearer errors and a schema view for the MCP ``query_data_collections`` tool.

The tool comes from django-mcp-server (``mcp_server.query_tool``). When a query
names a field or collection that does not exist, the library passes Django's
error through, and Django's ``FieldError`` lists every model field, including
ones the CRM does not publish. ``install()`` wraps the library's query method
so such errors become one line that names the bad field, suggests a published
one, and lists only published fields. Every other error, and every successful
result, is passed through unchanged.

``describe_collection()`` returns the published schema of one collection, built
with the library's own ``generate_json_schema`` so it matches what the query
tool publishes.
"""
import difflib
import json
import re

from django.core.exceptions import FieldDoesNotExist, FieldError


# Names agents commonly try, keyed by (collection, name); '*' matches any
# collection. ('field', target) suggests a published field and is used only
# when the target is published on that collection. ('hint', text) explains
# where the information lives instead.
_PDF_HINT = 'no stored PDF link; call generate_contract_pdf / generate_quote_pdf / generate_invoice_pdf'
FIELD_ALIASES = {
    ('*', 'legal_name'): ('field', 'legal_entity_name'),
    ('contact', 'first_name'): ('field', 'name'),
    ('contact', 'last_name'): ('field', 'name'),
    ('contact', 'full_name'): ('field', 'name'),
    ('*', 'branch_number'): ('field', 'branch'),
    ('*', 'invoice_date'): ('field', 'issue_date'),
    ('opportunity', 'value'): ('field', 'expected_value'),
    ('opportunity', 'contact'): ('hint', 'opportunities have no contact field; query contact by company'),
    ('quote', 'customer_contact_email'): ('field', 'contact'),
    ('task', 'contact'): ('field', 'related_contact'),
    ('company', 'address'): ('field', 'address_line1'),
    ('company', 'full_address'): ('field', 'address_line1'),
    ('zone', 'is_active'): ('hint', 'zones have no active flag; use status and is_orphaned'),
    ('zone', 'platform_type'): ('field', 'platform'),
    ('*', 'pdf_url'): ('hint', _PDF_HINT),
    ('*', 'preamble_template_name'): ('hint', 'use preamble_template with a $lookup on contracttemplate'),
    ('*', 'customer_company_name'): ('hint', 'use company with a $lookup on company'),
}

COLLECTION_ALIASES = {
    'servicelocation': 'contractservicelocation',
    'template': 'contracttemplate',
}

# Library ValueErrors that are about a field reference (query_tool.py).
_FIELD_VALUE_ERRORS = ('Invalid field path', 'Invalid localField', 'Unknown match key')


# ------------------------------------------------------------------ registry


def published_collections():
    """Collections of the global MCP server, keyed like query_data_collections."""
    from mcp_server.djangomcp import global_mcp_server
    from mcp_server.query_tool import ModelQueryToolsetMeta

    return {
        cls.model._meta.model_name.lower(): cls
        for cls in ModelQueryToolsetMeta.registry.values()
        if cls.model is not None and cls.mcp_server in (None, global_mcp_server)
    }


def collection_schema(cls):
    from mcp_server.query_tool import generate_json_schema

    return generate_json_schema(cls.model, fields=cls.fields, exclude=cls.get_excluded_fields())


def published_fields(cls):
    return list(collection_schema(cls)['$jsonSchema']['properties'])


# ------------------------------------------------------------------ messages


def _normalise(name):
    return re.sub(r'[\s_\-]', '', name.lower())


def suggest_collection(name, collections):
    collections = list(collections)
    norm = _normalise(name)
    candidates = [norm]
    for suffix, replacement in (('ies', 'y'), ('es', ''), ('s', '')):
        if norm.endswith(suffix):
            candidates.append(norm[:-len(suffix)] + replacement)
    for candidate in candidates:
        target = COLLECTION_ALIASES.get(candidate, candidate)
        if target in collections:
            return target
    close = difflib.get_close_matches(norm, collections, n=1)
    return close[0] if close else None


def unknown_collection_message(name, collections):
    collections = list(collections)
    suggestion = suggest_collection(str(name), collections)
    did_you_mean = f" Did you mean '{suggestion}'?" if suggestion else ''
    return f"Unknown collection '{name}'.{did_you_mean} Collections: {', '.join(collections)}"


def field_alias(collection, name, published):
    """The alias entry for a name on a collection, or None."""
    for key in ((collection, name), ('*', name)):
        alias = FIELD_ALIASES.get(key)
        if alias is None:
            continue
        kind, value = alias
        if kind == 'hint' or value in published:
            return alias
    return None


def suggest_field(collection, name, published):
    """('field', name), ('hint', text) or None. Only published names are suggested."""
    alias = field_alias(collection, name, published)
    if alias:
        return alias
    close = difflib.get_close_matches(name, published, n=1)
    return ('field', close[0]) if close else None


def unknown_field_message(name, collection, published, on_collection=True):
    suggestion = suggest_field(collection, name, published)
    where = 'on' if on_collection else 'in query on'
    text = f"Unknown field '{name}' {where} collection '{collection}'."
    if suggestion and suggestion[0] == 'field':
        text += f" Did you mean '{suggestion[1]}'?"
    elif suggestion:
        text += f" Hint: {suggestion[1]}."
    if published:
        text += f" Published fields: {', '.join(published)}"
    return text


# ------------------------------------------------------------------ locating a bad field


def _match_refs(match):
    if not isinstance(match, dict):
        return
    for key, value in match.items():
        if key in ('$and', '$or', '$nor') and isinstance(value, list):
            for cond in value:
                yield from _match_refs(cond)
        elif not key.startswith('$'):
            yield key


def _group_refs(group):
    for key, value in group.items():
        if key == '_id':
            values = value.values() if isinstance(value, dict) else [value]
        elif isinstance(value, dict):
            values = value.values()
        else:
            continue
        for ref in values:
            if isinstance(ref, str) and ref.startswith('$'):
                yield ref[1:]


def _field_refs(pipeline):
    """Every field path the pipeline names, as written by the caller."""
    for stage in pipeline if isinstance(pipeline, list) else []:
        if not isinstance(stage, dict):
            continue
        for op, body in stage.items():
            if op == '$lookup' and isinstance(body, dict) and isinstance(body.get('localField'), str):
                yield body['localField']
            elif op == '$match':
                yield from _match_refs(body)
            elif op == '$sort' and isinstance(body, dict):
                yield from body.keys()
            elif op == '$project' and isinstance(body, dict):
                for key, spec in body.items():
                    if isinstance(spec, str) and spec.startswith('$'):
                        yield spec[1:]
                    elif spec:
                        yield key
            elif op == '$group' and isinstance(body, dict):
                yield from _group_refs(body)


def _lookup_aliases(pipeline):
    """The alias map the library builds from $lookup stages (same rules)."""
    from mcp_server.query_tool import _translate_field

    aliases = {}
    for stage in pipeline if isinstance(pipeline, list) else []:
        lookup = stage.get('$lookup') if isinstance(stage, dict) else None
        if not isinstance(lookup, dict):
            continue
        try:
            local_field = _translate_field(lookup['localField'], aliases)
            aliases[lookup['as']] = {'prefix': local_field.replace('_id', ''), 'foreign_field': None}
        except (KeyError, TypeError, ValueError):
            continue
    return aliases


def _is_lookup(field, name):
    """True when name is a lookup or transform Django accepts after a relation (e.g. company__in)."""
    for getter in ('get_lookup', 'get_transform'):
        try:
            if getattr(field, getter)(name) is not None:
                return True
        except (AttributeError, TypeError):
            continue
    return False


def _unknown_part(model, path):
    """(model, name) for the first segment of a Django path that is not a field, else None."""
    current, previous = model, None
    for part in path.split('__'):
        if part == 'pk':
            return None
        try:
            field = current._meta.get_field(part)
        except FieldDoesNotExist:
            if previous is not None and _is_lookup(previous, part):
                return None
            return current, part
        if not (field.is_relation and field.related_model is not None):
            return None  # what follows is a lookup or transform on a plain field
        current, previous = field.related_model, field
    return None


def locate_unknown_field(base_cls, pipeline):
    """One-line message for the first unknown field the pipeline names, or None."""
    from mcp_server.query_tool import _translate_field

    aliases = _lookup_aliases(pipeline)
    collections = published_collections()
    for ref in _field_refs(pipeline):
        if not isinstance(ref, str) or ref == '_id':
            continue
        try:
            path = _translate_field(ref, aliases)
        except ValueError:
            continue  # unknown $lookup alias: the library message already says so
        found = _unknown_part(base_cls.model, path)
        if found is None:
            continue
        model, name = found
        collection = model._meta.model_name
        cls = collections.get(collection)
        return unknown_field_message(name, collection, published_fields(cls) if cls else [])
    return None


def field_error_message(base_cls, pipeline, exc):
    """A one-line message for a Django FieldError that never lists unpublished fields."""
    located = locate_unknown_field(base_cls, pipeline)
    if located:
        return located
    collection = base_cls.model._meta.model_name
    text = ' '.join(str(exc).split())
    keyword = re.search(r"Cannot resolve keyword '([^']+)' into field", text)
    if keyword:
        return unknown_field_message(keyword.group(1), collection, published_fields(base_cls), on_collection=False)
    if 'Choices are' in text:
        # Django lists every model field after "Choices are"; drop it.
        text = text.split('Choices are')[0].strip()
        return f"{text} Published fields: {', '.join(published_fields(base_cls))}"
    return text


# ------------------------------------------------------------------ the wrapper


def install():
    """Wrap the library's query method once. Results of valid queries are untouched."""
    from mcp_server import query_tool

    original = query_tool._QueryExecutor.query
    if getattr(original, '_crm_clear_errors', False):
        return

    def query(self, collection: str, search_pipeline: list[dict] = []):
        models = self.query_tool_models
        if isinstance(collection, str) and collection.lower() not in models:
            raise ValueError(unknown_collection_message(collection, models.keys()))
        try:
            return original(self, collection, search_pipeline)
        except FieldError as exc:
            raise ValueError(field_error_message(models[collection.lower()], search_pipeline, exc)) from exc
        except ValueError as exc:
            if str(exc).startswith(_FIELD_VALUE_ERRORS):
                located = locate_unknown_field(models[collection.lower()], search_pipeline)
                if located:
                    raise ValueError(located) from exc
            raise

    query._crm_clear_errors = True
    query.__wrapped__ = original
    query_tool._QueryExecutor.query = query


# ------------------------------------------------------------------ describe_collection


def collection_alias_hints(collection, published):
    hints = []
    for (scope, name), (kind, value) in FIELD_ALIASES.items():
        if scope not in ('*', collection) or name in published:
            continue
        if kind == 'field' and value not in published:
            continue
        hints.append({'name': name, 'use': value} if kind == 'field' else {'name': name, 'hint': value})
    return hints


def describe_collection(name):
    collections = published_collections()
    key = name.lower() if isinstance(name, str) else name
    cls = collections.get(key)
    if cls is None:
        raise ValueError(unknown_collection_message(name, collections.keys()))
    properties = collection_schema(cls)['$jsonSchema']['properties']
    fields = []
    for field_name, prop in properties.items():
        entry = {'name': field_name, 'type': prop.get('bsonType')}
        if 'enum' in prop:
            entry['choices'] = prop['enum']
        if 'ref' in prop:
            ref_model = cls.model._meta.get_field(field_name).related_model
            entry['ref'] = ref_model._meta.model_name
        if prop.get('description'):
            entry['description'] = str(prop['description'])
        fields.append(entry)
    return json.dumps({
        'collection': key,
        'fields': fields,
        'text_search_fields': sorted(cls.get_text_search_fields()),
        'extra_operators': [f'${op}' for op in (cls.extra_filters or [])],
        'extra_instructions': cls.extra_instructions or '',
        'alias_hints': collection_alias_hints(key, list(properties)),
    })
