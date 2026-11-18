"""Capture rules: internal domains, freemail, never-log rules, skip labels.

Pure functions over plain values. ``Rule`` mirrors a ``CaptureRule`` row so
the matcher and the sync engine can work on a snapshot.
"""
from dataclasses import dataclass

from .parse import domain_in


# The built-in Gmail label any user can apply to keep a thread out of the CRM.
PRIVATE_LABEL_NAME = 'crm private'

# Gmail system labels whose messages are never captured.
SKIP_SYSTEM_LABELS = frozenset({
    'SPAM', 'TRASH', 'DRAFT', 'CHAT',
    'CATEGORY_PROMOTIONS', 'CATEGORY_SOCIAL', 'CATEGORY_FORUMS',
})

# Public mail providers: a sender here is never matched by domain.
FREEMAIL_DOMAINS = frozenset({
    'gmail.com', 'googlemail.com', 'outlook.com', 'hotmail.com', 'live.com', 'msn.com',
    'yahoo.com', 'ymail.com', 'rocketmail.com', 'aol.com', 'icloud.com', 'me.com',
    'mac.com', 'proton.me', 'protonmail.com', 'pm.me', 'gmx.com', 'gmx.net', 'gmx.de',
    'mail.com', 'zoho.com', 'yandex.com', 'yandex.ru', 'mail.ru', 'qq.com', '163.com',
    '126.com', 'sina.com', 'naver.com', 'daum.net', 'hanmail.net', 'web.de',
    'hotmail.co.uk', 'hotmail.fr', 'hotmail.co.th', 'live.co.uk', 'outlook.co.th',
    'yahoo.co.uk', 'yahoo.co.th', 'yahoo.co.jp', 'yahoo.com.hk', 'yahoo.com.sg',
    'yahoo.co.id', 'yahoo.com.vn', 'yahoo.com.au', 'hotmail.com.au', 'bigpond.com',
    'tutanota.com', 'fastmail.com', 'hey.com', 'inbox.com', 'rediffmail.com',
})

ACTION_SKIP = 'skip'
ACTION_PRIVATE = 'private'
ACTION_HEADERS_ONLY = 'headers_only'
_DROP_ACTIONS = (ACTION_SKIP, ACTION_PRIVATE)


@dataclass(frozen=True)
class Rule:
    kind: str            # address | domain | label
    value: str           # lower-case for address/domain; label name as stored
    action: str          # skip | private | headers_only
    mailbox_id: object = None   # None for organisation-wide rules

    def applies_to_mailbox(self, mailbox_id):
        return self.mailbox_id is None or str(self.mailbox_id) == str(mailbox_id)


def rule_from_row(row):
    return Rule(
        kind=row.kind,
        value=row.value.lower() if row.kind != 'label' else row.value,
        action=row.action,
        mailbox_id=row.mailbox_id if row.scope == 'mailbox' else None,
    )


def is_freemail(domain, extra=()):
    domain = (domain or '').lower()
    return domain in FREEMAIL_DOMAINS or domain in extra


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
                if rule.action in _DROP_ACTIONS:
                    return rule.action
                hit = rule.action
    return hit


def private_label_ids(labels_by_id, rules, mailbox_id):
    """Ids of this mailbox's labels that keep a copy out: the built-in
    ``CRM private`` label and every label rule with a drop action."""
    names = {PRIVATE_LABEL_NAME}
    for rule in rules:
        if rule.kind == 'label' and rule.action in _DROP_ACTIONS and rule.applies_to_mailbox(mailbox_id):
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
