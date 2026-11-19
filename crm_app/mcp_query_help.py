"""Published-field boundary, clearer errors and a schema view for ``query_data_collections``.

The tool comes from django-mcp-server (``mcp_server.query_tool``). On its own
the library uses a toolset's ``fields`` only to write the schema text: it
returns every column when a query has no ``$project`` and follows any ``__``
path in ``$match``, ``$project``, ``$sort`` and ``$group``. ``install()`` wraps
the library's query method so that the published fields become the boundary:

* Before anything runs, every field path in the pipeline must resolve step by
  step through published fields of published collections (``Boundary.validate``).
  A relation step is allowed only when the relation is published and its target
  is a published collection. Anything else is refused with the same one-line
  "Unknown field ..." error whether or not the name exists on the model.
* The output is limited to published fields: a query without an effective
  ``$project`` gets one appended that lists the collection's published columns
  (``Boundary.restrict_output``), so the library itself builds
  ``values(<published columns>)``.
* Some fields are never published, whatever a toolset lists (``never_publish_reason``).

If the wrapper cannot be installed (for example after a library upgrade),
``install()`` logs one error and the query tool refuses every call instead of
running unchecked; see ``boundary_active()`` and ``crm_app.mcp_query_guard``.

``describe_collection()`` returns the published schema of one collection.
"""
import difflib
import fnmatch
import json
import logging
import re

from django.core.exceptions import FieldDoesNotExist, FieldError

logger = logging.getLogger(__name__)

# The wrapper is written against this exact library version. Any other version
# leaves the query tool refusing every call until the wrapper is re-verified.
SUPPORTED_LIBRARY = ('django-mcp-server', '0.5.7')

QUERY_UNAVAILABLE_MESSAGE = (
    'query_data_collections is unavailable: its published-field checks are not active on this server. '
    'Use get_commercial_document_context or the REST API, and report this to the CRM maintainers.'
)

PIPELINE_SHAPE_MESSAGE = 'search_pipeline must be a list of objects (pipeline stages); use [] for all rows.'

QUERY_TOOL = 'query_data_collections'

_STATE = {'installed': False}


class QueryInputError(ValueError):
    """A mistake in the caller's query, refused by the checks here. The message goes back to
    the agent unchanged; ``kind`` and ``name`` (the unknown field or collection) are for the
    one-line log entry."""

    def __init__(self, message, kind, name=None):
        super().__init__(message)
        self.kind = kind
        self.name = name


# The known validation sites: the functions (module, name) where the library and Django
# raise when the caller's pipeline is malformed or a value does not fit. An exception of
# one of _CALLER_INPUT_TYPES counts as a caller mistake only when its INNERMOST frame is
# one of these; anything else, database errors included, is a fault and keeps its traceback.
_VALIDATION_SITES = {
    # the library reading the stages (its raise sites, and the dict/str access on a stage)
    ('mcp_server.query_tool', 'apply_json_mango_query'): 'invalid_pipeline',
    ('mcp_server.query_tool', '_parse_match'): 'invalid_pipeline',
    ('mcp_server.query_tool', '_translate_field'): 'invalid_pipeline',
    ('mcp_server.query_tool', '_interpret_projection'): 'invalid_pipeline',
    ('mcp_server.query_tool', '_validate_lookup'): 'invalid_pipeline',
    ('mcp_server.query_tool', '_resolve_model_from_path'): 'invalid_pipeline',
    # Django converting a filter value for a column, or the value of an operator
    ('django.db.models.fields', 'to_python'): 'invalid_value',
    ('django.db.models.fields', 'get_prep_value'): 'invalid_value',
    ('django.db.models.lookups', 'get_prep_lookup'): 'invalid_value',
    # Django slicing for $skip / $limit
    ('django.db.models.query', '__getitem__'): 'invalid_skip_or_limit',
}
_CALLER_INPUT_TYPES = (ValueError, TypeError, AttributeError, KeyError)


def innermost_site(exc):
    """(module, function, line) of the frame that raised exc, or None."""
    tb = exc.__traceback__
    if tb is None:
        return None
    while tb.tb_next is not None:
        tb = tb.tb_next
    frame = tb.tb_frame
    return frame.f_globals.get('__name__', '?'), frame.f_code.co_name, tb.tb_lineno


def caller_input_kind(exc):
    """The kind of caller mistake an exception from the query tool is, or None for a fault.

    Our own refusals are QueryInputError. Otherwise only _CALLER_INPUT_TYPES (and Django's
    ValidationError) count, and only when raised at one of _VALIDATION_SITES.
    """
    from django.core.exceptions import ValidationError

    if isinstance(exc, QueryInputError):
        return exc.kind
    if not isinstance(exc, _CALLER_INPUT_TYPES + (ValidationError,)):
        return None
    site = innermost_site(exc)
    return _VALIDATION_SITES.get(site[:2]) if site else None


def loggable(value, limit=80):
    """A caller-supplied name, safe for a one-line log entry.

    Quoted like repr(), which escapes every character that is not printable: control
    characters, DEL, U+0085, U+2028/2029 and the other line and paragraph separators, and
    format characters such as bidi overrides, so the result never breaks the line. Longer
    names are cut at `limit` characters with a marker saying how many were left out.
    """
    text = value if isinstance(value, str) else repr(value)
    shown = repr(text[:limit])
    if len(text) > limit:
        shown += f'...(+{len(text) - limit} chars)'
    return shown


def _principal(request):
    user = getattr(request, 'user', None)
    return getattr(user, 'username', None) or '-'


def caller_mistake_log_line(exc, kind, principal, collection):
    """The one WARNING line for a refused query: no traceback, no values.

    Our own refusals name the unknown field or collection. A mistake recognised by its
    exception type also carries the type and the site that raised it, so a real bug that
    happens to look like a caller mistake can still be found without re-running it.
    """
    line = (f'{QUERY_TOOL} refused a query: kind={kind} principal={loggable(principal)} '
            f'collection={loggable(collection)}')
    if isinstance(exc, QueryInputError):
        if exc.name is not None:
            line += f' name={loggable(exc.name)}'
        return line
    module, function, lineno = innermost_site(exc)
    return line + f' error={type(exc).__name__} site={module}.{function}:{lineno}'


def tool_error_result(exc):
    """The reply the MCP SDK would build from the exception (FastMCP's ToolError text)."""
    from mcp.types import CallToolResult, TextContent

    return CallToolResult(content=[TextContent(type='text', text=f'Error executing tool {QUERY_TOOL}: {exc}')],
                          isError=True)


# ------------------------------------------------------------------ never publish

NEVER_PUBLISH_NAMES = frozenset({
    'password', 'token', 'secret', 'api_key', 'unsubscribe_token', 'tracking_token',
})
NEVER_PUBLISH_PATTERNS = ('*_password', '*_token', '*_secret', 'smtp_*')


def protected_models():
    """Models that are never a query target: the user model and the API token models."""
    from django.contrib.auth import get_user_model

    models = {get_user_model()}
    try:
        from rest_framework.authtoken.models import Token
        models.add(Token)
    except Exception:  # pragma: no cover - authtoken is installed in this project
        pass
    return models


def is_protected_model(model):
    concrete = getattr(model._meta, 'concrete_model', model)
    return any(concrete is protected._meta.concrete_model for protected in protected_models())


def _is_encrypted(field):
    field_type = type(field)
    return 'encrypted' in field_type.__module__.lower() or field_type.__name__.startswith('Encrypted')


def never_publish_reason(model, field):
    """Why a field may never be published or traversed, or None."""
    if is_protected_model(model):
        return 'protected model'
    name = field.name
    if name in NEVER_PUBLISH_NAMES or any(fnmatch.fnmatchcase(name, p) for p in NEVER_PUBLISH_PATTERNS):
        return 'protected name'
    if _is_encrypted(field):
        return 'encrypted field'
    related = getattr(field, 'related_model', None)
    if field.is_relation and related is not None and is_protected_model(related):
        return 'relation to a protected model'
    return None


# ------------------------------------------------------------------ aliases and messages

# Names agents commonly try, keyed by (collection, name); '*' matches any
# collection. ('field', target) suggests a published field and is used only
# when the target is published on that collection. ('hint', text) explains
# where the information lives instead.
_PDF_HINT = 'no stored PDF link; call generate_contract_pdf / generate_quote_pdf / generate_invoice_pdf'
_DOCUMENTS_HINT = "Contract documents are a separate collection: query contractdocument with contract = the contract's id"
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
    ('company', 'currency'): ('hint', 'currency is set on each contract, quote and invoice; a company has billing_entity'),
    ('company', 'primary_contact'): ('hint', 'query contact with this company and is_primary true'),
    ('*', 'number_of_zones'): ('hint', 'count contractservicelocation rows by contract (one per zone or custom '
                                       'item) or zone rows by company; company.contracted_zone_count is the '
                                       'contracted count'),
    ('contract', 'contract_documents'): ('hint', _DOCUMENTS_HINT),
    ('contract', 'documents'): ('hint', _DOCUMENTS_HINT),
    ('contract', 'quote'): ('hint', "a contract's source quote is not published; query quote by company"),
    ('contract', 'source_quote'): ('hint', "a contract's source quote is not published; query quote by company"),
    ('quote', 'sent_date'): ('hint', 'quote send dates are not published; status shows whether it was sent'),
    ('*', 'payment_method'): ('hint', 'payment method is not published; use status and paid_date on invoice'),
}

COLLECTION_ALIASES = {
    'servicelocation': 'contractservicelocation',
    'document': 'contractdocument',
    'template': 'contracttemplate',
}


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
    """('field', name), ('hint', text) or None. Depends only on the name and published fields."""
    alias = field_alias(collection, name, published)
    if alias:
        return alias
    close = difflib.get_close_matches(name, published, n=1)
    return ('field', close[0]) if close else None


def unknown_field_message(name, collection, published, on_collection=True):
    name = str(name)
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


# ------------------------------------------------------------------ the boundary


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


def _is_lookup(field, name):
    """True when name is a lookup or transform Django applies to this field (e.g. company__in)."""
    for getter in ('get_lookup', 'get_transform'):
        try:
            if getattr(field, getter)(name) is not None:
                return True
        except (AttributeError, TypeError):
            continue
    return False


# The library handles one operator per stage, the first of these it finds
# (apply_json_mango_query's if/elif chain); other keys in that stage are ignored.
_STAGE_ORDER = ('$match', '$search', '$sort', '$skip', '$limit', '$project', '$group', '$lookup')


def _effective_op(stage):
    for op in _STAGE_ORDER:
        if op in stage:
            return op
    return None


class Boundary:
    """The published fields of a set of collections, and the checks that enforce them."""

    def __init__(self, collections):
        self.collections = dict(collections)
        self.collection_of = {cls.model: name for name, cls in self.collections.items()}
        self.fields = {}
        for name, cls in self.collections.items():
            keep = []
            for field_name in collection_schema(cls)['$jsonSchema']['properties']:
                field = cls.model._meta.get_field(field_name)
                if never_publish_reason(cls.model, field):
                    continue
                if field.is_relation and (field.related_model not in self.collection_of
                                          or is_protected_model(field.related_model)):
                    continue
                keep.append(field_name)
            self.fields[name] = keep

    def output_columns(self, collection):
        """Published concrete columns in model order, keyed like queryset.values()."""
        model = self.collections[collection].model
        published = set(self.fields[collection])
        return [f.attname for f in model._meta.concrete_fields if f.name in published]

    def search_fields_published(self, collection):
        searchable = self.collections[collection].get_text_search_fields() or ()
        return set(searchable) <= set(self.fields[collection])

    # -------------------------------------------------------------- paths

    def _refuse(self, name, collection):
        return QueryInputError(unknown_field_message(name, collection, self.fields[collection]),
                               'unknown_field', name)

    def check_path(self, collection, path):
        """Raise the one-line error unless a Django field path stays on published fields.

        Each step must be a published concrete field of the current collection.
        A relation moves to its target collection (always published, by
        construction of self.fields). After a plain field the rest of the path
        is lookups and transforms on that column, which Django validates and
        which cannot join another table.
        """
        if not isinstance(path, str):
            raise self._refuse(path, collection)
        model = self.collections[collection].model
        parts = path.split('__')
        previous_relation = None
        for index, part in enumerate(parts):
            current = self.collection_of[model]
            published = self.fields[current]
            if part == 'pk':
                field = model._meta.pk
            else:
                try:
                    field = model._meta.get_field(part)
                except FieldDoesNotExist:
                    field = None
            if field is None and previous_relation is not None and _is_lookup(previous_relation, part):
                return  # a lookup on the relation's key, e.g. company__in
            if field is None or not field.concrete or field.name not in published:
                raise self._refuse(part, current)
            if not field.is_relation:
                return
            rest = parts[index + 1:]
            if part not in (field.name, 'pk') or not rest:
                # The key value itself (company or company_id), optionally with one lookup.
                if rest and not (len(rest) == 1 and _is_lookup(field, rest[0])):
                    raise self._refuse(rest[0], self.collection_of[field.related_model])
                return
            model = field.related_model
            previous_relation = field

    def _translate(self, path, aliases):
        from mcp_server.query_tool import _translate_field

        return _translate_field(path, aliases)  # unknown alias: the library's own ValueError

    def _check_match(self, collection, match, aliases, top):
        if not isinstance(match, dict):
            return
        for key, condition in match.items():
            if key in ('$and', '$or', '$nor'):
                for cond in condition if isinstance(condition, list) else []:
                    self._check_match(collection, cond, aliases, top=False)
            elif key == '$text' and top:
                self._check_search(collection)
            else:
                self.check_path(collection, self._translate(key, aliases))

    def _check_search(self, collection):
        if not self.search_fields_published(collection):
            raise QueryInputError(f"Full text search is not available on collection '{collection}'.",
                                  'search_unavailable')

    def _check_ref(self, collection, ref, aliases):
        if isinstance(ref, str) and ref.startswith('$'):
            path = ref[1:]
            self.check_path(collection, 'pk' if path == '_id' else self._translate(path, aliases))

    def validate(self, collection, pipeline):
        """Check every field path in the pipeline before anything runs."""
        if not isinstance(pipeline, list):
            return
        stages = [stage for stage in pipeline if isinstance(stage, dict)]
        aliases = {}
        # $lookup aliases, built in order exactly as the library builds them.
        for stage in stages:
            lookup = stage.get('$lookup')
            if not isinstance(lookup, dict):
                continue
            local = lookup.get('localField')
            if not isinstance(local, str):
                continue
            local_path = self._translate(local, aliases)
            self.check_path(collection, local_path)
            if isinstance(lookup.get('as'), str):
                aliases[lookup['as']] = {'prefix': local_path.replace('_id', ''),
                                         'foreign_field': lookup.get('foreignField')}
        for stage in stages:
            for op, body in stage.items():
                if op == '$match':
                    self._check_match(collection, body, aliases, top=True)
                elif op == '$search':
                    self._check_search(collection)
                elif op == '$sort' and isinstance(body, dict):
                    for key in body:  # the library passes $sort keys to order_by as written
                        self.check_path(collection, key[1:] if isinstance(key, str) and key.startswith('-') else key)
                elif op == '$project' and isinstance(body, dict):
                    for key, spec in body.items():
                        if isinstance(spec, str) and spec.startswith('$'):
                            self._check_ref(collection, spec, aliases)
                        elif spec:
                            self._check_ref(collection, '$' + key, aliases)
                elif op == '$group' and isinstance(body, dict):
                    for key, value in body.items():
                        refs = value.values() if isinstance(value, dict) else [value]
                        if key != '_id' and not isinstance(value, dict):
                            continue
                        for ref in refs:
                            self._check_ref(collection, ref, aliases)

    # -------------------------------------------------------------- output

    def restrict_output(self, collection, pipeline):
        """The pipeline to run: unchanged when its output is already explicit, else with a
        final $project of the published columns.

        $group output is built only from validated paths. Otherwise the library
        uses the last $project stage that includes at least one field, and falls
        back to every column. Appending a $project makes the library itself
        build values(<published columns>) for that fallback.
        """
        if not isinstance(pipeline, list):
            return pipeline
        effective = [(_effective_op(stage), stage) for stage in pipeline if isinstance(stage, dict)]
        if any(op == '$group' for op, _ in effective):
            return pipeline
        last = None
        for op, stage in effective:
            if op == '$project':
                last = stage['$project']
        if isinstance(last, dict) and any(bool(spec) for spec in last.values()):
            return pipeline
        return list(pipeline) + [{'$project': {column: 1 for column in self.output_columns(collection)}}]


_BOUNDARIES = {}


def boundary_for(collections):
    key = tuple(sorted((name, id(cls)) for name, cls in collections.items()))
    boundary = _BOUNDARIES.get(key)
    if boundary is None:
        boundary = _BOUNDARIES[key] = Boundary(collections)
    return boundary


def published_fields(cls):
    """The published field names of one toolset class, in schema order."""
    collections = published_collections()
    name = cls.model._meta.model_name.lower()
    if collections.get(name) is not cls:
        collections = {name: cls}
    return list(boundary_for(collections).fields[name])


def field_error_message(boundary, collection, exc):
    """A one-line message for a Django FieldError that never lists unpublished fields."""
    text = ' '.join(str(exc).split())
    published = boundary.fields[collection]
    keyword = re.search(r"Cannot resolve keyword '([^']+)' into field", text)
    if keyword:
        return unknown_field_message(keyword.group(1), collection, published, on_collection=False)
    if 'Choices are' in text:
        # Django lists every model field after "Choices are"; drop it.
        return f"{text.split('Choices are')[0].strip()} Published fields: {', '.join(published)}"
    return text


# ------------------------------------------------------------------ installation


def _library_version():
    from importlib.metadata import version

    return version(SUPPORTED_LIBRARY[0])


def boundary_active():
    """True only while the boundary wrapper is the library's query method."""
    try:
        from mcp_server import query_tool

        return bool(_STATE['installed']) and getattr(query_tool._QueryExecutor.query, '_crm_boundary', False)
    except Exception:
        return False


def _install():
    found = _library_version()
    if found != SUPPORTED_LIBRARY[1]:
        raise RuntimeError(f'{SUPPORTED_LIBRARY[0]} {found} is not the verified {SUPPORTED_LIBRARY[1]}')
    from mcp_server import query_tool

    for name in ('_QueryExecutor', 'ModelQueryToolsetMeta', 'generate_json_schema', '_translate_field'):
        getattr(query_tool, name)
    original = query_tool._QueryExecutor.query
    if getattr(original, '_crm_boundary', False):
        return

    def checked_query(self, collection, search_pipeline):
        # Checked first, so the field checks never depend on the library's argument model.
        if not isinstance(search_pipeline, list) or not all(isinstance(s, dict) for s in search_pipeline):
            raise QueryInputError(PIPELINE_SHAPE_MESSAGE, 'pipeline_shape')
        collections = self.query_tool_models
        if not isinstance(collection, str) or collection.lower() not in collections:
            raise QueryInputError(unknown_collection_message(collection, collections.keys()),
                                  'unknown_collection', collection)
        name = collection.lower()
        boundary = boundary_for(collections)
        boundary.validate(name, search_pipeline)
        pipeline = boundary.restrict_output(name, search_pipeline)
        try:
            return original(self, collection, pipeline)
        except FieldError as exc:
            keyword = re.search(r"Cannot resolve keyword '([^']+)' into field", str(exc))
            raise QueryInputError(field_error_message(boundary, name, exc),
                                  'unknown_field' if keyword else 'field_error',
                                  keyword.group(1) if keyword else None) from exc

    def query(self, collection: str, search_pipeline: list[dict] = []):
        try:
            return checked_query(self, collection, search_pipeline)
        except Exception as exc:
            kind = caller_input_kind(exc)
            # Only a call through the MCP tool carries a context. There a caller mistake is
            # answered as the SDK would answer the exception (same text, isError), without
            # reaching the library's handler, which logs every exception with a traceback.
            # In-process callers keep getting the exception.
            if self.context is None or kind is None:
                raise
            logger.warning('%s', caller_mistake_log_line(exc, kind, _principal(self.request), collection))
            return tool_error_result(exc)

    query._crm_boundary = True
    query.__wrapped__ = original
    query_tool._QueryExecutor.query = query


def _refuse_registered_tool():
    """Best effort: make the registered tool refuse in-process calls too."""
    try:
        from mcp_server.djangomcp import global_mcp_server

        tool = global_mcp_server._tool_manager.get_tool('query_data_collections')
        if tool is None:
            return

        async def refuse(*args, **kwargs):
            raise ValueError(QUERY_UNAVAILABLE_MESSAGE)

        tool.fn = refuse
    except Exception:
        pass


def install():
    """Install the boundary. Never raises: on failure the query tool refuses every call."""
    try:
        _install()
    except Exception as exc:
        _STATE['installed'] = False
        logger.error('MCP query boundary not installed (%s: %s); query_data_collections will refuse every call.',
                     type(exc).__name__, exc)
        _refuse_registered_tool()
        return False
    _STATE['installed'] = True
    return True


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
        raise QueryInputError(unknown_collection_message(name, collections.keys()), 'unknown_collection', name)
    published = boundary_for(collections).fields[key]
    properties = collection_schema(cls)['$jsonSchema']['properties']
    fields = []
    for field_name in published:
        prop = properties[field_name]
        entry = {'name': field_name, 'type': prop.get('bsonType')}
        if 'enum' in prop:
            entry['choices'] = prop['enum']
        if 'ref' in prop:
            entry['ref'] = cls.model._meta.get_field(field_name).related_model._meta.model_name
        if prop.get('description'):
            entry['description'] = str(prop['description'])
        fields.append(entry)
    return json.dumps({
        'collection': key,
        'fields': fields,
        'text_search_fields': sorted(cls.get_text_search_fields()),
        'extra_operators': [f'${op}' for op in (cls.extra_filters or [])],
        'extra_instructions': cls.extra_instructions or '',
        'alias_hints': collection_alias_hints(key, published),
    })
