"""Propose company mail domains from the email addresses of existing contacts.

At launch ``CompanyDomain`` is empty, so a reply on a confirmed thread from a
customer's colleague who is not yet a contact can only be proposed. This
command derives domains from contacts:

* freemail, public-suffix and our own domains are skipped;
* a domain used by contacts of exactly one company is proposed for it;
* a domain used by contacts of several companies is proposed only when those
  companies share a corporate parent (one is the parent of the others, or
  all have the same parent), and then as a shared group domain on each, which
  never auto-matches; otherwise it is skipped;
* domains already recorded for that company are left alone.

``--dry-run`` (the default) prints counts only. ``--apply`` writes the
proposed rows. It writes only ``CompanyDomain`` rows, reads no mailbox and
calls no Gmail API.
"""
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models.functions import Lower

from crm_app.models import Company, Contact

from mail_capture import conf
from mail_capture.models import CompanyDomain
from mail_capture.parse import address_domain, domain_in, normalise_address
from mail_capture.rules import company_domain_problem, is_freemail


NOTE = 'Seeded from contact email domains'


def plan_domains():
    """(proposals, counts). Proposals are (company id, domain, shared) tuples."""
    internal = conf.internal_domains()
    by_domain = defaultdict(set)
    counts = defaultdict(int)
    for company_id, email in Contact.objects.annotate(e=Lower('email')).values_list('company_id', 'e'):
        domain = address_domain(normalise_address(email or ''))
        if not domain:
            counts['contacts_without_domain'] += 1
            continue
        if is_freemail(domain):
            counts['contacts_on_freemail'] += 1
            continue
        if domain_in(domain, internal):
            counts['contacts_on_our_domains'] += 1
            continue
        if company_domain_problem(domain, internal):
            counts['contacts_on_refused_domains'] += 1
            continue
        by_domain[domain].add(company_id)
    parents = dict(Company.objects.values_list('id', 'parent_company_id'))
    existing = set(CompanyDomain.objects.values_list('company_id', 'domain'))
    proposals = []
    for domain, companies in sorted(by_domain.items()):
        counts['domains_considered'] += 1
        shared = len(companies) > 1
        if shared and not _share_a_parent(companies, parents):
            counts['domains_skipped_several_companies'] += 1
            continue
        for company_id in sorted(companies, key=str):
            if (company_id, domain) in existing:
                counts['already_recorded'] += 1
                continue
            proposals.append((company_id, domain, shared))
            counts['proposed_shared_group' if shared else 'proposed_single_company'] += 1
    return proposals, dict(counts)


def _share_a_parent(companies, parents):
    groups = set()
    for company_id in companies:
        parent = parents.get(company_id)
        groups.add(parent if parent else company_id)
    # One group: all children of one parent, or the parent plus its children.
    if len(groups) == 1:
        return True
    roots = {g for g in groups if g in companies}
    return len(roots) == 1 and all(parents.get(c) in roots or c in roots for c in companies)


class Command(BaseCommand):
    help = 'Propose company mail domains from contacts (dry run by default; --apply writes).'

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument('--dry-run', action='store_true', default=True, help='Counts only (default)')
        mode.add_argument('--apply', action='store_true', help='Write the proposed CompanyDomain rows')

    def handle(self, *args, **options):
        proposals, counts = plan_domains()
        for key in sorted(counts):
            self.stdout.write(f'{key}: {counts[key]}')
        if not options['apply']:
            self.stdout.write(f'would write: {len(proposals)} (dry run, nothing changed)')
            return
        with transaction.atomic():
            rows = [CompanyDomain(company_id=c, domain=d, shared_group_domain=s, note=NOTE)
                    for c, d, s in proposals]
            for row in rows:
                row.save()
        self.stdout.write(f'written: {len(rows)}')
