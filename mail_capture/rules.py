"""Capture rules: internal domains, freemail, never-log rules, skip labels.

Pure functions over plain values. ``Rule`` mirrors a ``CaptureRule`` row so
the matcher and the sync engine can work on a snapshot.
"""
from dataclasses import dataclass

from django.conf import settings

from .parse import domain_in
from .public_suffixes import SECOND_LEVELS as _PSL_SECOND_LEVELS, WILDCARD_COUNTRY_CODES


# The built-in Gmail label any user can apply to keep a thread out of the CRM.
PRIVATE_LABEL_NAME = 'crm private'

# Gmail system labels whose messages are never captured.
SKIP_SYSTEM_LABELS = frozenset({
    'SPAM', 'TRASH', 'DRAFT', 'CHAT',
    'CATEGORY_PROMOTIONS', 'CATEGORY_SOCIAL', 'CATEGORY_FORUMS',
})
# A stored copy that later gets one of these is dropped as if deleted.
DROP_ON_LABEL = frozenset({'SPAM', 'TRASH'})

# Gmail system label names a label rule may not use: they would match nearly
# every message.
SYSTEM_LABEL_NAMES = frozenset({
    'inbox', 'sent', 'important', 'starred', 'unread', 'draft', 'spam', 'trash', 'chat',
    'category_personal', 'category_social', 'category_promotions', 'category_updates',
    'category_forums',
})

# Public mail providers: a sender here is never matched by domain, and such a
# domain cannot be a company domain. Extend with CAPTURE_EXTRA_FREEMAIL_DOMAINS.
FREEMAIL_DOMAINS = frozenset({
    # global
    'gmail.com', 'googlemail.com', 'outlook.com', 'hotmail.com', 'live.com', 'msn.com',
    'windowslive.com', 'yahoo.com', 'ymail.com', 'rocketmail.com', 'aol.com', 'icloud.com',
    'me.com', 'mac.com', 'proton.me', 'protonmail.com', 'pm.me', 'gmx.com', 'gmx.net', 'gmx.de',
    'mail.com', 'zoho.com', 'yandex.com', 'yandex.ru', 'mail.ru', 'web.de', 'tutanota.com',
    'fastmail.com', 'hey.com', 'inbox.com', 'rediffmail.com',
    # regional variants of the big providers
    'hotmail.co.uk', 'hotmail.fr', 'hotmail.co.th', 'hotmail.co.jp', 'hotmail.com.au',
    'live.co.uk', 'live.com.sg', 'live.com.au', 'outlook.co.th', 'outlook.jp', 'outlook.sg',
    'yahoo.co.uk', 'yahoo.co.th', 'yahoo.co.jp', 'yahoo.com.hk', 'yahoo.com.sg', 'yahoo.co.id',
    'yahoo.com.vn', 'yahoo.com.au', 'yahoo.com.tw', 'yahoo.com.my', 'yahoo.com.ph',
    'yahoo.co.in',
    # China, Korea, Japan
    'qq.com', 'foxmail.com', '163.com', '126.com', 'yeah.net', '139.com', 'sina.com', 'sina.cn',
    'sohu.com', 'aliyun.com', 'naver.com', 'daum.net', 'hanmail.net', 'nate.com', 'kakao.com',
    # ISP mail in the region
    'bigpond.com', 'bigpond.net.au', 'optusnet.com.au', 'singnet.com.sg', 'netvigator.com',
    'pacific.net.sg', 'starhub.net.sg', 'tm.net.my', 'streamyx.com', 'truemail.co.th',
})

# Public suffixes, embedded (not the full Public Suffix List; no dependency).
# A domain is refused for rules, company domains and internal domains unless
# it has more labels than its public suffix, i.e. it is at least a registrable
# domain ("hotel.co.th", never "co.th" or "th"), and unless every label is
# non-empty ("co..th" is refused).
#
# Covered: the generic second levels of every country code in the Public
# Suffix List (``public_suffixes.py``: source, version and filter stated
# there; e.g. co.za, com.br, co.uk, com.au), the wildcard country codes
# (every second level of .ck, .er, .fk, .jm, .mm, .np, .pg), and the
# hand-written zones below for the countries the company sells in (which add
# non-generic ones such as in.th, mi.th, my.id). Not covered: deeper or
# city-level rules (for example the Japanese prefecture zones or *.kawasaki.jp)
# and the PSL's private section beyond SHARED_PLATFORM_SUFFIXES. Confirmation
# is still required before any rule purges.
_COUNTRY_SECOND_LEVELS = {
    'th': 'co ac go in or net mi',
    'hk': 'com org net edu gov idv',
    'sg': 'com org net edu gov per',
    'my': 'com org net edu gov mil name biz',
    'id': 'co or ac web go net sch my biz mil ponpes desa',
    'vn': 'com org net edu gov int biz info name pro health ac',
    'ph': 'com org net edu gov mil ngo i',
    'mv': 'com org net edu gov mil aero biz coop info museum name pro',
    'lk': 'com org net edu gov int sch ngo soc web grp hotel ltd',
    'in': 'co net org firm gen ind ac edu res gov mil nic',
    'ae': 'co net org ac gov mil sch',
    'au': 'com net org edu gov asn id csiro',
    'jp': 'co ne or ac ad ed go gr lg',
    'kr': 'co ne or re pe go mil ac hs ms es sc kg',
    'tw': 'com net org edu gov mil idv',
    'cn': 'com net org edu gov ac mil',
    'mo': 'com net org edu gov',
    'mm': 'com net org edu gov',
    'kh': 'com net org edu gov mil per',
    'la': 'com net org edu gov per int',
    'uk': 'co org ac gov me ltd plc net nhs sch',
    'nz': 'co org net ac govt school',
}
MULTI_PART_SUFFIXES = frozenset(
    f'{second}.{tld}'
    for table in (_COUNTRY_SECOND_LEVELS, _PSL_SECOND_LEVELS)
    for tld, seconds in table.items() for second in seconds.split()
)
# Shared hosting and tenant domains: every customer of the platform sits under them.
SHARED_PLATFORM_SUFFIXES = frozenset({
    'onmicrosoft.com', 'mail.onmicrosoft.com', 'googlegroups.com', 'blogspot.com',
    'appspot.com', 'herokuapp.com', 'github.io', 'azurewebsites.net', 'cloudfront.net',
    'amazonaws.com', 'wixsite.com', 'myshopify.com',
})
PUBLIC_SUFFIXES = MULTI_PART_SUFFIXES | SHARED_PLATFORM_SUFFIXES


def public_suffix_of(domain):
    """The longest embedded public suffix of ``domain`` (one label when no
    multi-part suffix applies)."""
    labels = (domain or '').lower().strip('.').split('.')
    for size in (3, 2):
        if len(labels) >= size and '.'.join(labels[-size:]) in PUBLIC_SUFFIXES:
            return '.'.join(labels[-size:])
    if len(labels) >= 2 and labels[-1] in WILDCARD_COUNTRY_CODES:
        return '.'.join(labels[-2:])
    return labels[-1] if labels else ''


ACTION_SKIP = 'skip'
ACTION_PRIVATE = 'private'
ACTION_HEADERS_ONLY = 'headers_only'
DROP_ACTIONS = (ACTION_SKIP, ACTION_PRIVATE)


@dataclass(frozen=True)
class Rule:
    kind: str            # address | domain | label
    value: str           # lower-case for address/domain; label name as stored
    action: str          # skip | private | headers_only
    mailbox_id: object = None   # None for organisation-wide rules
    pk: object = None
    confirmed: bool = False     # may purge stored mail (blocking new capture needs no confirmation)
    # Label rules: the stored copies (ids as text) the confirmation covers.
    purge_copy_ids: frozenset = frozenset()

    def applies_to_mailbox(self, mailbox_id):
        return self.mailbox_id is None or str(self.mailbox_id) == str(mailbox_id)


def extra_freemail():
    return frozenset(
        str(d).strip().lower() for d in getattr(settings, 'CAPTURE_EXTRA_FREEMAIL_DOMAINS', ()) or ()
        if str(d).strip()
    )


def is_freemail(domain, extra=None):
    domain = (domain or '').lower()
    if extra is None:
        extra = extra_freemail()
    return domain in FREEMAIL_DOMAINS or domain in extra


def is_public_suffix(domain):
    """True when ``domain`` is not at least a registrable domain: empty, a
    single label, or no more labels than its public suffix."""
    domain = (domain or '').lower().strip('.')
    if not domain or '.' not in domain:
        return True
    if any(not label for label in domain.split('.')):
        return True    # an empty label ("co..th") is never a registrable domain
    suffix = public_suffix_of(domain)
    return len(domain.split('.')) <= len(suffix.split('.'))


def rule_problem(kind, value, internal_domains=None):
    """Why a rule value is refused, or '' when it is acceptable."""
    from . import conf
    internal = tuple(internal_domains if internal_domains is not None else conf.internal_domains())
    value = (value or '').strip()
    if not value:
        return 'A rule needs a value.'
    if any(c in value for c in '*%? \t\r\n,;'):
        return 'Wildcards, spaces and lists are not allowed; add one rule per value.'
    if kind == 'label':
        if value.lower() in SYSTEM_LABEL_NAMES or value.upper().startswith('CATEGORY_'):
            return 'A Gmail system label would match almost every message.'
        return ''
    if kind == 'address':
        if value.count('@') != 1 or not value.split('@')[0] or '.' not in value.split('@')[1]:
            return 'An address rule needs one full address, such as name@company.example.'
        return ''
    if kind == 'domain':
        if is_public_suffix(value):
            return 'This is a public suffix or has no dot; it would match a whole registry.'
        if domain_in(value, internal) or any(domain_in(d, (value,)) for d in internal):
            return 'This is (or contains) one of our own domains; it would match every message.'
        if is_freemail(value):
            return 'This is a public mail provider; use address rules for its users.'
        return ''
    return 'Unknown rule kind.'


def company_domain_problem(domain, internal_domains=None):
    from . import conf
    internal = tuple(internal_domains if internal_domains is not None else conf.internal_domains())
    if is_public_suffix(domain):
        return 'This is a public suffix or has no dot.'
    if is_freemail(domain):
        return 'A public mail provider cannot identify a company.'
    if domain_in(domain, internal):
        return 'This is one of our own domains.'
    return ''


def internal_domain_problem(domain):
    if is_public_suffix(domain):
        return 'public suffix'
    if is_freemail(domain):
        return 'freemail provider'
    return ''


def rule_from_row(row):
    return Rule(
        kind=row.kind,
        value=row.value.lower() if row.kind != 'label' else row.value,
        action=row.action,
        mailbox_id=row.mailbox_id if row.scope == 'mailbox' else None,
        pk=row.pk,
        confirmed=row.is_confirmed,
        purge_copy_ids=frozenset(str(x) for x in (row.purge_copy_ids or ()))
        if row.kind == 'label' else frozenset(),
    )


def _address_rule_hits(rule, address, domain, match_key):
    if rule.kind == 'address':
        return rule.value in (address, match_key)
    if rule.kind == 'domain':
        return domain_in(domain, (rule.value,))
    return False


def message_rule_action(addresses, rules, mailbox_id):
    """Strongest address/domain rule action for a message, or None.

    ``addresses`` are ``parse.Address`` objects. A drop action (skip/private)
    beats ``headers_only``. Rules scoped to another mailbox are ignored.
    """
    hit = None
    for rule in rules:
        if rule.kind == 'label' or not rule.applies_to_mailbox(mailbox_id):
            continue
        for item in addresses:
            if _address_rule_hits(rule, item.address, item.domain, item.match_key):
                if rule.action in DROP_ACTIONS:
                    return rule.action
                hit = rule.action
    return hit


def private_label_ids(labels_by_id, rules, mailbox_id, confirmed_only=False):
    """Ids of this mailbox's labels that keep a copy out: the built-in
    ``CRM private`` label and every label rule with a drop action.

    With ``confirmed_only`` (what may remove stored copies), rule labels count
    only once their rule was confirmed; the built-in label always counts."""
    names = {PRIVATE_LABEL_NAME}
    for rule in rules:
        if rule.kind == 'label' and rule.action in DROP_ACTIONS and rule.applies_to_mailbox(mailbox_id) \
                and (rule.confirmed or not confirmed_only):
            names.add(rule.value.strip().lower())
    return frozenset(
        label_id for label_id, name in (labels_by_id or {}).items()
        if str(name).strip().lower() in names
    )


def headers_only_label_ids(labels_by_id, rules, mailbox_id, confirmed_only=False):
    names = {
        rule.value.strip().lower() for rule in rules
        if rule.kind == 'label' and rule.action == ACTION_HEADERS_ONLY
        and rule.applies_to_mailbox(mailbox_id) and (rule.confirmed or not confirmed_only)
    }
    return frozenset(
        label_id for label_id, name in (labels_by_id or {}).items()
        if str(name).strip().lower() in names
    )


def label_purge_maps(labels_by_id, rules, mailbox_id):
    """What may remove or strip copies already stored in this mailbox:

    * ``builtin``: ids of the built-in ``CRM private`` label (any copy carrying
      it goes, at once);
    * ``drop``: ``{label id: copy ids}`` for confirmed label rules with a drop
      action. Only the copies the confirmation covered (the previewed set) may
      go; others carrying the label wait for a new preview;
    * ``strip``: the same for confirmed headers-only label rules (bodies).
    """
    names = {}
    for label_id, name in (labels_by_id or {}).items():
        names.setdefault(str(name).strip().lower(), set()).add(label_id)
    builtin = frozenset(names.get(PRIVATE_LABEL_NAME, ()))
    drop, strip = {}, {}
    for rule in rules:
        if rule.kind != 'label' or not rule.confirmed or not rule.applies_to_mailbox(mailbox_id):
            continue
        target = drop if rule.action in DROP_ACTIONS else strip if rule.action == ACTION_HEADERS_ONLY else None
        if target is None:
            continue
        for label_id in names.get(rule.value.strip().lower(), ()):
            target[label_id] = frozenset(target.get(label_id, frozenset()) | rule.purge_copy_ids)
    return builtin, drop, strip


COPY_KEEP = 'keep'
COPY_SKIP_SYSTEM = 'skip_system'
COPY_PRIVATE = 'private'


def copy_decision(label_ids, private_ids):
    """Whether one mailbox's copy of a message may be captured, from its labels."""
    labels = set(label_ids or ())
    if labels & private_ids:
        return COPY_PRIVATE
    if labels & SKIP_SYSTEM_LABELS:
        return COPY_SKIP_SYSTEM
    return COPY_KEEP
