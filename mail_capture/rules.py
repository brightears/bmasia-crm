"""Capture rules: internal domains, freemail, never-log rules, skip labels.

Pure functions over plain values. ``Rule`` mirrors a ``CaptureRule`` row so
the matcher and the sync engine can work on a snapshot.
"""
from dataclasses import dataclass

from django.conf import settings

from .parse import domain_in


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

# A short list of public suffixes (not the full Public Suffix List; no new
# dependency). A rule, company domain or internal domain equal to one of
# these, or without any dot, would match a whole country or registry.
PUBLIC_SUFFIXES = frozenset({
    'com', 'net', 'org', 'edu', 'gov', 'mil', 'int', 'info', 'biz', 'io', 'co', 'me', 'asia',
    'app', 'dev', 'test', 'example', 'invalid', 'local', 'localhost', 'onion',
    'th', 'hk', 'sg', 'my', 'id', 'ph', 'vn', 'kh', 'la', 'mm', 'cn', 'tw', 'jp', 'kr', 'in',
    'au', 'nz', 'uk', 'de', 'fr', 'it', 'es', 'nl', 'ch', 'ae', 'us', 'ca', 'eu',
    'co.th', 'ac.th', 'go.th', 'in.th', 'or.th', 'net.th', 'mi.th',
    'com.hk', 'org.hk', 'net.hk', 'edu.hk', 'gov.hk', 'idv.hk',
    'com.sg', 'org.sg', 'net.sg', 'edu.sg', 'gov.sg',
    'com.my', 'org.my', 'net.my', 'co.id', 'or.id', 'com.ph', 'com.vn', 'com.kh',
    'com.cn', 'net.cn', 'org.cn', 'com.tw', 'org.tw', 'co.jp', 'ne.jp', 'or.jp', 'ac.jp',
    'co.kr', 'or.kr', 'co.in', 'org.in', 'com.au', 'net.au', 'org.au', 'co.nz',
    'co.uk', 'org.uk', 'ac.uk', 'gov.uk', 'co.ae',
})

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
    domain = (domain or '').lower().strip('.')
    return not domain or '.' not in domain or domain in PUBLIC_SUFFIXES


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


def private_label_ids(labels_by_id, rules, mailbox_id):
    """Ids of this mailbox's labels that keep a copy out: the built-in
    ``CRM private`` label and every label rule with a drop action."""
    names = {PRIVATE_LABEL_NAME}
    for rule in rules:
        if rule.kind == 'label' and rule.action in DROP_ACTIONS and rule.applies_to_mailbox(mailbox_id):
            names.add(rule.value.strip().lower())
    return frozenset(
        label_id for label_id, name in (labels_by_id or {}).items()
        if str(name).strip().lower() in names
    )


def headers_only_label_ids(labels_by_id, rules, mailbox_id):
    names = {
        rule.value.strip().lower() for rule in rules
        if rule.kind == 'label' and rule.action == ACTION_HEADERS_ONLY
        and rule.applies_to_mailbox(mailbox_id)
    }
    return frozenset(
        label_id for label_id, name in (labels_by_id or {}).items()
        if str(name).strip().lower() in names
    )


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
