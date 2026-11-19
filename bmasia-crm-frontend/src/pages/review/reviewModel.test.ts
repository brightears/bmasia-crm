import {
  CardState,
  cardActions,
  friendlyRefusal,
  describeLink,
  hasUnusualSpaces,
  mixesDirections,
  needsSourceCheck,
  textWarnings,
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
      { text: '', marker: 'U+202E', kind: 'invisible' },
      { text: 'b' },
      { text: '', marker: 'U+200B', kind: 'invisible' },
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

  it('round-trips the URL state, and never puts a user name into it', () => {
    const q = readQuery(
      new URLSearchParams(
        'tab=decided&company=c1&kind=note&proposer=sample-bot&evidence=unverified&decided=rejected&sort=expiring',
      ),
    );
    expect(q).toEqual({
      tab: 'decided',
      company: 'c1',
      kind: 'note',
      evidence: 'unverified',
      decided: 'rejected',
      sort: 'expiring',
    });
    expect(writeQuery(q).toString()).toBe(
      'tab=decided&company=c1&kind=note&evidence=unverified&decided=rejected&sort=expiring',
    );
    expect(writeQuery(q).toString()).not.toContain('sample-bot');
    expect(readQuery(new URLSearchParams('tab=bogus')).tab).toBe('open');
    expect(writeQuery(readQuery(new URLSearchParams(''))).toString()).toBe('');
  });
});

describe('what can be done to a card (the one rule for buttons and keys)', () => {
  const free: CardState = {
    readOnly: null,
    expired: false,
    busy: false,
    decided: false,
    editing: false,
    acknowledged: false,
    conflictChoice: null,
    partnersShown: true,
    sourceChecked: false,
  };
  const conflict = {
    id: 'o',
    proposer_username: 'other',
    patch: { phone: '1' },
    evidence_occurred_at: null,
    created_at: '',
  };

  it('allows everything on a plain open suggestion', () => {
    const a = cardActions(makeProposal(), free);
    expect([a.accept.ok, a.edit.ok, a.acceptEdits.ok, a.reject.ok, a.select.ok]).toEqual([
      true,
      true,
      false,
      true,
      true,
    ]);
  });

  it('while editing, only "accept with edits" and reject remain', () => {
    const a = cardActions(makeProposal(), { ...free, editing: true });
    expect(a.accept).toEqual({ ok: false, reason: 'Finish or cancel the edit first.' });
    expect(a.acceptEdits.ok).toBe(true);
    expect(a.select.ok).toBe(false);
  });

  it('the changed-record tick gates accept, edit and accept with edits', () => {
    const p = makeProposal({ target_changed_at: '2026-11-18T00:00:00Z' });
    [cardActions(p, free), cardActions(p, { ...free, editing: true })].forEach((a) => {
      expect(a.accept.ok || a.edit.ok || a.acceptEdits.ok).toBe(false);
    });
    expect(cardActions(p, free).accept.reason).toMatch(/I have compared the current values/);
    expect(cardActions(p, { ...free, acknowledged: true }).accept.ok).toBe(true);
    expect(cardActions(p, free).reject.ok).toBe(true);
  });

  it('a conflict needs the other evidence shown and a choice, on every accepting route', () => {
    const p = makeProposal({ conflicts_with: [conflict] });
    expect(cardActions(p, { ...free, partnersShown: false, conflictChoice: 'this' }).accept.reason).toMatch(
      /evidence is shown/,
    );
    expect(cardActions(p, free).edit.reason).toMatch(/Choose which/);
    expect(cardActions(p, { ...free, editing: true }).acceptEdits.ok).toBe(false);
    expect(cardActions(p, { ...free, conflictChoice: 'this' }).accept.ok).toBe(true);
  });

  it('an email or phone change without captured evidence needs the source tick', () => {
    const weak = makeProposal({ evidence: 'verified_agent_recorded', patch: { email: 'a@example.com' } });
    expect(needsSourceCheck(weak)).toBe(true);
    expect(cardActions(weak, free).accept.reason).toMatch(/checked this against the source/);
    expect(cardActions(weak, { ...free, sourceChecked: true }).accept.ok).toBe(true);
    expect(needsSourceCheck(makeProposal({ evidence: 'verified_captured', patch: { phone: '1' } }))).toBe(false);
    expect(needsSourceCheck(makeProposal({ evidence: 'unverified', patch: { city: 'X' } }))).toBe(false);
  });

  it('read-only, expired, busy and decided cards allow nothing', () => {
    const p = makeProposal();
    (
      [
        [{ readOnly: 'Not yours.' }, 'Not yours.'],
        [{ expired: true }, 'This suggestion has expired.'],
        [{ busy: true }, 'Waiting for the answer to the last decision.'],
        [{ decided: true }, 'Already decided on this page.'],
      ] as [Partial<CardState>, string][]
    ).forEach(([patch, reason]) => {
      const a = cardActions(p, { ...free, ...patch });
      expect([a.accept.ok, a.edit.ok, a.reject.ok, a.select.ok]).toEqual([false, false, false, false]);
      expect(a.accept.reason).toBe(reason);
    });
  });
});

describe('text checks', () => {
  it('marks tag, filler and variation characters, and unusual spaces', () => {
    const tag = String.fromCodePoint(0xe0041);
    expect(segmentText(`a${tag}b`)).toEqual([
      { text: 'a' },
      { text: '', marker: 'U+E0041', kind: 'invisible' },
      { text: 'b' },
    ]);
    expect(
      segmentText('x\u034Fy')
        .map((s) => s.marker)
        .filter(Boolean),
    ).toEqual(['U+034F']);
    expect(
      segmentText('a\u00A0b')
        .map((s) => s.marker)
        .filter(Boolean),
    ).toEqual(['U+00A0']);
    expect(segmentText(' a  b ', true).map((s) => s.marker || s.text)).toEqual(['\u2423', 'a  b', '\u2423']);
    expect(hasUnusualSpaces('Bangkok  Noi')).toBe(true);
    expect(hasUnusualSpaces('Bangkok Noi')).toBe(false);
  });

  it('tells mixed writing directions apart from look-alike letters', () => {
    expect(textWarnings('\u05DE\u05E0\u05D4\u05DC 123 Manager')).toEqual(['direction']);
    expect(textWarnings('Jo T\u0430n')).toEqual(['lookalike']);
    expect(textWarnings('Plain value')).toEqual([]);
    expect(textWarnings('Plain value', true)).toEqual(['server_mixed']);
    expect(mixesDirections('\u05DE\u05E0\u05D4\u05DC')).toBe(false);
  });

  it('shows where a link goes and refuses unusual addresses', () => {
    expect(describeLink('https://mail.google.com/mail/u/0/#inbox/1')).toMatchObject({
      host: 'mail.google.com',
      registrable: 'google.com',
      prefix: 'mail.',
      label: 'Open in Gmail',
    });
    expect(describeLink('https://mail.google.com.example.net/x')).toMatchObject({
      registrable: 'example.net',
      label: 'Open link',
    });
    expect(describeLink('https://intranet.example.co.th/a')).toMatchObject({
      registrable: 'example.co.th',
      prefix: 'intranet.',
    });
    [
      ['https://mail.google.com@phish.example/login', /user name or an @/],
      ['https://user:pass@example.com/', /user name or an @/],
      ['https://xn--ggle-0nda.example/', /punycode/],
      ['https://g\u043Eogle.example/', /non-ASCII/],
      [`${JS}alert(1)`, /not an http/],
      ['HTTPS://example.com', /not an http/],
    ].forEach(([url, reason]) => {
      const info = describeLink(url as string)!;
      expect(info.href).toBeNull();
      expect(info.refused).toMatch(reason as RegExp);
    });
  });
});

describe('confirmation round', () => {
  it('reads "Open in Gmail" only for exactly mail.google.com', () => {
    expect(describeLink('https://mail.google.com/mail/u/0/')!.label).toBe('Open in Gmail');
    expect(describeLink('https://accounts.google.com/x')!.label).toBe('Open link');
    expect(describeLink('https://mail.google.com.other.example/x')!.label).toBe('Open link');
    expect(describeLink('https://mail.google.com./x')!.label).toBe('Open link');
  });

  it('a trailing dot does not make "com." the owner', () => {
    expect(describeLink('https://mail.google.com./x')).toMatchObject({ registrable: 'google.com', prefix: 'mail.' });
  });

  it('puts refusals in plain words, without setting names', () => {
    expect(friendlyRefusal('anything', 'review_not_configured')).toBe(
      'Reviewing is not set up yet. Ask an administrator.',
    );
    expect(friendlyRefusal('x', undefined, false)).toBe('Reviewing is not set up yet. Ask an administrator.');
    expect(friendlyRefusal('Your account is not on the reviewer list (SOME_SETTING_NAME).')).toBe(
      'Your account is not on the reviewer list.',
    );
    expect(friendlyRefusal('A reviewer must be a different person from the proposer.')).toBe(
      'A reviewer must be a different person from the proposer.',
    );
  });

  it('a failed contact look-up or a failed partner blocks accepting until resolved', () => {
    const base: CardState = {
      readOnly: null,
      expired: false,
      busy: false,
      decided: false,
      editing: false,
      acknowledged: false,
      conflictChoice: null,
      partnersShown: true,
      sourceChecked: false,
    };
    const p = makeProposal({ target_collection: 'contact', patch: { title: 'X' } });
    expect(cardActions(p, { ...base, contactCheck: 'pending' }).accept.reason).toMatch(/Checking whether/);
    expect(cardActions(p, { ...base, contactCheck: 'failed' }).accept.reason).toMatch(/checked this contact myself/);
    expect(cardActions(p, { ...base, contactCheck: 'failed', contactChecked: true }).accept.ok).toBe(true);
    const c = makeProposal({
      conflicts_with: [{ id: 'o', proposer_username: 'o', patch: {}, evidence_occurred_at: null, created_at: '' }],
    });
    expect(cardActions(c, { ...base, partnersShown: false, partnersFailed: true }).accept.reason).toMatch(
      /Retry first/,
    );
  });
});
