import test from 'node:test';
import assert from 'node:assert/strict';
import { loadPlatformPostings, loadPlatformSnapshot, loadPlatformInvoice } from '../src/platform.js';

const invoice = (id = 1, status = 'received') => ({
  id, status, seller_name: 'Demo Fuel Station', seller_nip: '1234567890',
  description: 'Fuel for company vehicle', ksef_number: `MOCK-${id}`,
  issue_date: '2026-11-05', received_at: '2026-11-05T10:00:00Z',
  net: '200.00', vat: '46.00', gross: '246.00', vehicle_plate: null,
});
const caseRow = (id = 10, invoice_id = 1, status = 'open') => ({
  id, invoice_id, status, reason: 'Vehicle usage unknown', opened_by: 'invoice_agent',
  assignee: null, created_at: '2026-11-05T10:01:00Z', resolved_at: null,
});
const question = (id = 20, case_id = 10) => ({
  id, case_id, text: 'How is the vehicle used?', status: 'answered', answer: 'Mixed use',
  asked_by: 'regulations_agent', answered_by: 'client_agent',
  created_at: '2026-11-05T10:02:00Z', answered_at: '2026-11-05T10:03:00Z',
});
const event = (id = 1, invoice_id = 1, case_id = null) => ({
  id, invoice_id, case_id, at: '2026-11-05T10:00:00Z', actor: 'system',
  type: 'invoice.received', summary: 'Mock invoice received', data: {},
});
const client = { name: 'Demo Company', nip: '9876543210', fleet: [], facts: [] };
const posting = (invoice_id = 1) => ({
  id: invoice_id + 100, invoice_id, account: '403', rationale: 'Mixed use', actor: 'accountant',
  created_at: '2026-11-05T10:00:00Z', status: 'active', source: 'accountant',
  deductible_vat: '40.25', vat_deduction_percent: 50, legal_basis: null, reusable: true, conditions: {},
});
const snapshot = () => ({
  '/api/invoices': [invoice()], '/api/cases': [], '/api/questions': [],
  '/api/client': client, '/api/events': [event()],
});

function mockFetch(t, responses) {
  const calls = [];
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    calls.push({ url, options });
    assert.equal(options.method, 'GET');
    assert.deepEqual(options.headers, { Accept: 'application/json' });
    assert.ok(url.startsWith('/api/'));
    assert.equal(options.body, undefined);
    assert.ok(Object.hasOwn(responses, url), `Unexpected request: ${url}`);
    const payload = responses[url];
    if (payload instanceof Error) throw payload;
    if (typeof payload === 'function') return payload();
    return { ok: true, status: 200, json: async () => structuredClone(payload) };
  });
  return calls;
}

test('snapshot starts all five GETs concurrently, forwards signal and maps Decimal strings', async t => {
  const responses = snapshot();
  let release;
  responses['/api/invoices'] = () => new Promise(resolve => { release = () => resolve({ ok: true, json: async () => [invoice()] }); });
  const calls = mockFetch(t, responses);
  const controller = new AbortController();
  const pending = loadPlatformSnapshot({ signal: controller.signal });
  assert.deepEqual(calls.map(item => item.url), ['/api/invoices', '/api/cases', '/api/questions', '/api/client', '/api/events']);
  assert.ok(calls.every(call => call.options.signal === controller.signal));
  release();
  const result = await pending;
  const row = result.invoices[0];
  assert.equal(row.id, 'API-1'); assert.equal(row.apiId, 1);
  assert.equal(row.supplier, 'Demo Fuel Station'); assert.equal(row.initials, 'DF');
  assert.equal(row.amount, 246); assert.equal(row.netAmount, 200); assert.equal(row.vatAmount, 46);
  assert.equal(row.date, '2026-11-05'); assert.equal(row.status, 'received');
  assert.equal(row.context, 'Fuel for company vehicle'); assert.equal(row.origin, 'platform');
  assert.equal(row.raw.gross, '246.00');
  assert.deepEqual(result.client, client); assert.deepEqual(result.events, [event()]);
});

test('status follows posted, waiting case, open case and received without invented blocks', async t => {
  const responses = snapshot();
  responses['/api/invoices'] = [invoice(1, 'posted'), invoice(2, 'escalated'), invoice(3), invoice(4), invoice(5, 'escalated'), invoice(6)];
  responses['/api/cases'] = [caseRow(11, 1, 'waiting_for_client'), caseRow(12, 2, 'waiting_for_client'), caseRow(13, 3), caseRow(14, 6, 'resolved')];
  responses['/api/questions'] = [question(20, 12)];
  mockFetch(t, responses);
  const { invoices } = await loadPlatformSnapshot();
  assert.deepEqual(invoices.map(row => row.status), ['completed', 'waiting_for_client', 'in_review', 'received', 'in_review', 'received']);
  assert.deepEqual(invoices[1].questions, [question(20, 12)]);
  assert.deepEqual(invoices[0].questions, []);
});

test('empty platform stays empty, never populates demo fixtures', async t => {
  mockFetch(t, { ...snapshot(), '/api/invoices': [], '/api/events': [] });
  assert.deepEqual((await loadPlatformSnapshot()).invoices, []);
});

test('detail loads real case answers, postings and only matching timeline events', async t => {
  const raw = { ...invoice(1, 'posted'), cases: [caseRow()], postings: [{
    id: 30, invoice_id: 1, case_id: 10, account: '401', vat_deduction_percent: 50,
    deductible_vat: '23.00', rationale: 'Recorded demo decision', confidence: 0.9,
    actor: 'regulations_agent', source: 'regulation', precedent_id: null,
    legal_basis: 'Recorded demo legal reference', reusable: false, conditions: {},
    status: 'active', superseded_by: null, created_at: '2026-11-05T10:04:00Z',
  }] };
  const calls = mockFetch(t, {
    '/api/invoices/1': raw,
    '/api/cases/10': { ...caseRow(), invoice: invoice(), questions: [question()] },
    '/api/events': [event(), event(2, null, 10), event(3, 2), event(4, null)],
  });
  const detail = await loadPlatformInvoice(1);
  assert.deepEqual(detail.raw, raw); assert.deepEqual(detail.postings, raw.postings);
  assert.equal(detail.questions[0].answer, 'Mixed use');
  assert.deepEqual(detail.events.map(item => item.id), [1, 2]);
  assert.deepEqual(calls.map(item => item.url), ['/api/invoices/1', '/api/events', '/api/cases/10']);
});

test('HTTP errors, network errors, invalid JSON and cancellation are reported', async t => {
  for (const [name, response, expected] of [
    ['HTTP', () => ({ ok: false, status: 503 }), /HTTP 503/],
    ['network', new Error('Network offline'), /Network offline/],
    ['JSON', () => ({ ok: true, json: async () => { throw new SyntaxError('bad'); } }), /Invalid JSON/],
    ['abort', new DOMException('Cancelled', 'AbortError'), /Cancelled/],
  ]) await t.test(name, async t => {
    mockFetch(t, { ...snapshot(), '/api/invoices': response });
    await assert.rejects(loadPlatformSnapshot(), expected);
  });
});

test('malformed amounts, statuses and envelopes fail rather than becoming fake data', async t => {
  for (const [name, patch] of [
    ['blank amount', { gross: '' }], ['negative', { net: '-2.00' }],
    ['NaN', { vat: 'NaN' }], ['null', { gross: null }], ['precision', { gross: '2.123' }],
    ['status', { status: 'blocked' }], ['id', { id: '1' }], ['supplier', { seller_name: null }],
  ]) await t.test(name, async t => {
    mockFetch(t, { ...snapshot(), '/api/invoices': [{ ...invoice(), ...patch }] });
    await assert.rejects(loadPlatformSnapshot(), /Invalid platform response/);
  });
  await t.test('array envelope', async t => {
    mockFetch(t, { ...snapshot(), '/api/cases': { items: [] } });
    await assert.rejects(loadPlatformSnapshot(), /expected an array/);
  });
  await t.test('client envelope', async t => {
    mockFetch(t, { ...snapshot(), '/api/client': {} });
    await assert.rejects(loadPlatformSnapshot(), /\/client/);
  });
});

test('detail rejects invalid IDs before fetching, wrong relations and failed case reads', async t => {
  await t.test('invalid apiId', async t => {
    const calls = mockFetch(t, {});
    for (const value of [undefined, '1', -1, 1.5, '../reset']) await assert.rejects(loadPlatformInvoice(value), /apiId/);
    assert.equal(calls.length, 0);
  });
  await t.test('wrong invoice', async t => {
    mockFetch(t, { '/api/invoices/1': { ...invoice(2), cases: [], postings: [] }, '/api/events': [] });
    await assert.rejects(loadPlatformInvoice(1), /mismatch/);
  });
  await t.test('case failure', async t => {
    mockFetch(t, { '/api/invoices/1': { ...invoice(), cases: [caseRow()], postings: [] }, '/api/events': [], '/api/cases/10': () => ({ ok: false, status: 404 }) });
    await assert.rejects(loadPlatformInvoice(1), /HTTP 404/);
  });
  await t.test('question relation', async t => {
    mockFetch(t, { '/api/invoices/1': { ...invoice(), cases: [caseRow()], postings: [] }, '/api/events': [], '/api/cases/10': { ...caseRow(), invoice: invoice(), questions: [question(20, 99)] } });
    await assert.rejects(loadPlatformInvoice(1), /question relation mismatch/);
  });
});

test('postings for decisions and precedents come from each invoice detail and are validated', async t => {
  const calls = mockFetch(t, { '/api/invoices/2': { id: 2, postings: [posting(2)] } });
  assert.deepEqual(await loadPlatformPostings([{ apiId: 2 }]), [posting(2)]);
  assert.deepEqual(calls.map(call => call.url), ['/api/invoices/2']);
});

test('postings validate every input before fetching and keep an empty inbox empty', async t => {
  const calls = mockFetch(t, {});
  for (const input of [undefined, {}, [null], [{ apiId: '../reset' }], [{ apiId: 1 }, { apiId: '2' }], [{ apiId: 1 }, { apiId: 1 }]]) {
    await assert.rejects(loadPlatformPostings(input), /Invalid platform response/);
  }
  assert.deepEqual(await loadPlatformPostings([]), []);
  assert.equal(calls.length, 0);
});

test('postings reject missing invoices and invalid or unrelated decisions', async t => {
  for (const [name, payload, expected] of [
    ['missing invoice', () => ({ ok: false, status: 404 }), /HTTP 404/],
    ['wrong invoice', { id: 3, postings: [] }, /invoice id mismatch/],
    ['missing postings', { id: 2 }, /expected an array/],
    ['wrong relation', { id: 2, postings: [posting(3)] }, /invoice relation mismatch/],
    ['unknown source', { id: 2, postings: [{ ...posting(2), source: 'guess' }] }, /posting source/],
    ['missing reusable flag', { id: 2, postings: [{ ...posting(2), reusable: undefined }] }, /reusable/],
    ['invalid conditions', { id: 2, postings: [{ ...posting(2), conditions: [] }] }, /expected an object/],
  ]) await t.test(name, async t => {
    mockFetch(t, { '/api/invoices/2': payload });
    await assert.rejects(loadPlatformPostings([{ apiId: 2 }]), expected);
  });
});

test('postings bound concurrent detail requests and preserve order when responses finish out of order', async t => {
  const waiting = [];
  let active = 0;
  let peak = 0;
  t.mock.method(globalThis, 'fetch', async url => {
    active++;
    peak = Math.max(peak, active);
    const apiId = Number(url.split('/').at(-1));
    await new Promise(resolve => waiting.push(() => { active--; resolve(); }));
    return Response.json({ id: apiId, postings: [posting(apiId)] });
  });
  const invoices = Array.from({ length: 20 }, (_, index) => ({ apiId: index + 1 }));
  const pending = loadPlatformPostings(invoices);
  assert.equal(waiting.length, 6);
  while (waiting.length) {
    waiting.splice(0).reverse().forEach(resolve => resolve());
    await new Promise(resolve => setImmediate(resolve));
  }
  assert.equal(peak, 6);
  assert.deepEqual((await pending).map(row => row.invoice_id), invoices.map(row => row.apiId));
});

test('cancelled postings do not start requests and stop scheduling queued invoices', async t => {
  const controller = new AbortController();
  const waiting = [];
  const calls = mockFetch(t, Object.fromEntries(Array.from({ length: 20 }, (_, index) => [
    `/api/invoices/${index + 1}`, () => new Promise(resolve => waiting.push(() => resolve(Response.json({ id: index + 1, postings: [] })))),
  ])));
  const pending = loadPlatformPostings(Array.from({ length: 20 }, (_, index) => ({ apiId: index + 1 })), { signal: controller.signal });
  const rejected = assert.rejects(pending, { name: 'AbortError' });
  assert.equal(calls.length, 6);
  assert.ok(calls.every(call => call.options.signal === controller.signal));
  controller.abort();
  waiting.forEach(resolve => resolve());
  await rejected;
  assert.equal(calls.length, 6);
  await assert.rejects(loadPlatformPostings([{ apiId: 1 }], { signal: controller.signal }), { name: 'AbortError' });
  assert.equal(calls.length, 6);
});

test('failed postings stop scheduling queued invoices', async t => {
  const waiting = [];
  const calls = mockFetch(t, Object.fromEntries(Array.from({ length: 20 }, (_, index) => [
    `/api/invoices/${index + 1}`, () => new Promise(resolve => waiting.push(() => resolve(index === 0
      ? { ok: false, status: 404 }
      : Response.json({ id: index + 1, postings: [] })))),
  ])));
  const pending = loadPlatformPostings(Array.from({ length: 20 }, (_, index) => ({ apiId: index + 1 })));
  const rejected = assert.rejects(pending, /HTTP 404/);
  waiting.shift()();
  await rejected;
  waiting.forEach(resolve => resolve());
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(calls.length, 6);
});
