import {
  editableFields,
  groupProposals,
  hasInvisible,
  lookalikeScripts,
  needsAnotherLook,
  readOnlyReason,
  readQuery,
  safeHttpUrl,
  segmentText,
  validateValue,
  writeQuery,
} from './reviewModel';
import { makeProposal } from './testFixtures';

/** Built at run time so the source holds no script URL literal. */
const JS = ['java', 'script:'].join('');

describe('text safety', () => {
  it('shows invisible and direction-changing characters as markers', () => {
    expect(segmentText('a\u202Eb\u200Bc')).toEqual([
      { text: 'a' },
      { text: '', hidden: 'U+202E' },
      { text: 'b' },
      { text: '', hidden: 'U+200B' },
      { text: 'c' },
    ]);
    expect(segmentText('plain text')).toEqual([{ text: 'plain text' }]);
    expect(hasInvisible('x\u2066y')).toBe(true);
    expect(hasInvisible('ไทย ok')).toBe(false);
  });

  it('notices lookalike alphabets mixed in one value', () => {
    expect(lookalikeScripts('Jo T\u0430n')).toEqual(['Latin', 'Cyrillic']);
    expect(lookalikeScripts('Jo Tan')).toEqual([]);
    expect(lookalikeScripts('สมชาย Tan')).toEqual([]);
  });

  it('links only lowercase http and https URLs', () => {
    expect(safeHttpUrl('https://mail.example.com/m/1')).toBe('https://mail.example.com/m/1');
    expect(safeHttpUrl('http://example.com')).toBe('http://example.com/');
    [
      `${JS}alert(1)`,
      'data:text/html,x',
      `${JS.toUpperCase()}alert(1)`,
      ' https://x.example',
      'HTTPS://x.example',
      'https://x.example/\u202Efdp',
      'ftp://x.example',
      '//x.example',
      'mailto:a@b.example',
      '',
    ].forEach((bad) => expect(safeHttpUrl(bad)).toBeNull());
  });
});

describe('field rules as the API enforces them', () => {
  it.each([
    ['company', 'email', 'not-an-email', 'Not an email address.'],
    ['company', 'website', `${JS}alert(1)`, 'Must start with http:// or https://.'],
    ['contact', 'linkedin_url', 'www.example.com', 'Must start with http:// or https://.'],
    ['contact', 'phone', '+66 81 000', 'Digits only with an optional +, 9 to 15 digits.'],
    ['contact', 'preferred_contact_method', 'Fax', 'One of: Email, Phone, Mobile, LinkedIn.'],
    ['task', 'priority', 'Soon', 'One of: Low, Medium, High, Urgent.'],
    ['task', 'due_date', 'next week', 'Not a date and time.'],
    ['task', 'related_contact', 'abc', 'Not a record ID.'],
    ['company', 'postal_code', '1'.repeat(21), 'At most 20 characters.'],
    ['company', 'city', 'Bang\u202Ekok', 'One line only, without control or invisible characters.'],
    ['company', 'city', 'Bang\nkok', 'One line only, without control or invisible characters.'],
  ])('%s.%s refuses %j', (collection, key, value, message) => {
    expect(validateValue(collection, key, value)).toBe(message);
  });

  it.each([
    ['company', 'email', 'office@example.com'],
    ['company', 'website', 'https://example.com'],
    ['contact', 'phone', '+66810000001'],
    ['company', 'phone', '+66 2 000 0000'],
    ['task', 'due_date', '2026-11-20T09:00:00+07:00'],
    ['task', 'related_contact', '0f8e4c1a-1111-4222-8333-944455556666'],
    ['company', 'notes', 'two\nlines'],
    ['task', 'description', 'line one\nline two'],
    ['contact', 'name', 'สมชาย ใจดี'],
  ])('%s.%s accepts %j', (collection, key, value) => {
    expect(validateValue(collection, key, value)).toBeNull();
  });

  it('reads editable fields from the allowlist', () => {
    const settings = {
      kinds: { field_update: { company: ['phone', 'email'] } },
      proposals_enabled: true,
      activity_writes_enabled: false,
    };
    expect(editableFields(settings, 'field_update', 'company')).toEqual(['phone', 'email']);
    expect(editableFields(settings, 'note', 'company')).toBeNull();
  });
});

describe('queue rules', () => {
  it('groups by company, then batch, newest evidence first', () => {
    const rows = [
      makeProposal({
        id: 'a1',
        company_id: 'c1',
        company_name: 'Alpha',
        batch_key: 'b1',
        evidence_occurred_at: '2026-11-01T10:00:00Z',
      }),
      makeProposal({
        id: 'b1',
        company_id: 'c2',
        company_name: 'Beta',
        batch_key: '',
        evidence_occurred_at: '2026-11-05T10:00:00Z',
      }),
      makeProposal({
        id: 'a2',
        company_id: 'c1',
        company_name: 'Alpha',
        batch_key: 'b1',
        evidence_occurred_at: '2026-11-03T10:00:00Z',
      }),
      makeProposal({
        id: 'a3',
        company_id: 'c1',
        company_name: 'Alpha',
        batch_key: '',
        evidence_occurred_at: '2026-11-02T10:00:00Z',
      }),
    ];
    const groups = groupProposals(rows);
    expect(groups.map((g) => g.companyName)).toEqual(['Beta', 'Alpha']);
    expect(groups[1].batches.map((b) => b.proposals.map((p) => p.id))).toEqual([['a2', 'a1'], ['a3']]);
  });

  it('says why an open suggestion needs another look', () => {
    expect(needsAnotherLook(makeProposal())).toEqual([]);
    expect(
      needsAnotherLook(
        makeProposal({
          target_changed_at: '2026-11-18T00:00:00Z',
          last_apply_error: 'x',
          conflicts_with: [{ id: 'o', proposer_username: 'x', patch: {}, evidence_occurred_at: null, created_at: '' }],
        }),
      ),
    ).toEqual(['record_changed', 'conflict', 'apply_error']);
  });

  it('keeps the proposer and the evidence recorder from deciding', () => {
    expect(readOnlyReason(makeProposal({ proposer_username: 'Reviewer.One' }), 'reviewer.one', null)).toMatch(
      /You made this suggestion/,
    );
    expect(readOnlyReason(makeProposal({ evidence_recorded_by: 'reviewer.one' }), 'reviewer.one', null)).toMatch(
      /You recorded the evidence/,
    );
    expect(readOnlyReason(makeProposal(), 'reviewer.one', 'Not on the list.')).toBe('Not on the list.');
    expect(readOnlyReason(makeProposal(), 'reviewer.one', null)).toBeNull();
  });

  it('round-trips the URL state', () => {
    const q = readQuery(
      new URLSearchParams('tab=decided&company=c1&kind=note&proposer=theo&evidence=unverified&decided=rejected'),
    );
    expect(q).toEqual({
      tab: 'decided',
      company: 'c1',
      kind: 'note',
      proposer: 'theo',
      evidence: 'unverified',
      decided: 'rejected',
    });
    expect(writeQuery(q).toString()).toBe(
      'tab=decided&company=c1&kind=note&proposer=theo&evidence=unverified&decided=rejected',
    );
    expect(readQuery(new URLSearchParams('tab=bogus')).tab).toBe('open');
    expect(writeQuery(readQuery(new URLSearchParams(''))).toString()).toBe('');
  });
});
