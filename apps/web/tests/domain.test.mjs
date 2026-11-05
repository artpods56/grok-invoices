import test from 'node:test';
import assert from 'node:assert/strict';
import {
  createDemoInvoices, STATUS_LABELS, summarizeInvoices, filterInvoices,
  validateDemoAnswer, resolveDemoQuestion, exportInvoicesCsv,
} from '../src/domain.js';

const reply = { vehicleRegistration: ' demo 123 ', usage: 'mixed', purpose: ' Client visit ' };

function freezeDeep(value) {
  if (value && typeof value === 'object') {
    Object.values(value).forEach(freezeDeep);
    Object.freeze(value);
  }
  return value;
}

test('fixtures match the selected mock and each call owns all nested data', () => {
  const first = createDemoInvoices();
  assert.deepEqual(first.map(({ id, supplier, amount, context }) => [id, supplier, amount, context]), [
    ['DEMO-001', 'Demo IT Services', 615, 'IT services'],
    ['DEMO-002', 'Demo Fuel Station', 246, 'Known vehicle'],
    ['DEMO-003', 'Demo Fuel Station', 246, 'Unknown vehicle'],
    ['DEMO-004', 'Demo Supplier', 123, 'Missing context'],
  ]);
  assert.deepEqual(summarizeInvoices(first), { completed: 2, waiting_for_client: 1, blocked: 1, received: 0, in_review: 0, attention: 0 });
  assert.ok(first.every(row => row.date === '2026-11-05' && row.amount === row.netAmount + row.vatAmount));
  first[0].sources[0].note = 'changed';
  first[1].timeline[0].title = 'changed';
  first[2].status = 'completed';
  const second = createDemoInvoices();
  assert.notEqual(second[0].sources[0].note, 'changed');
  assert.notEqual(second[1].timeline[0].title, 'changed');
  assert.equal(second[2].status, 'waiting_for_client');
  assert.notEqual(second[0].sources[0], second[2].sources[1]);
});

test('filter and counts are pure, compose status with case-insensitive search, and handle empty sets', () => {
  const invoices = freezeDeep(createDemoInvoices());
  assert.deepEqual(filterInvoices(invoices, { query: ' FUEL ', status: 'completed' }).map(row => row.id), ['DEMO-002']);
  assert.deepEqual(filterInvoices(invoices, { query: 'demo-003' }).map(row => row.id), ['DEMO-003']);
  assert.deepEqual(filterInvoices(invoices, { query: 'unknown VEHICLE' }).map(row => row.id), ['DEMO-003']);
  assert.equal(filterInvoices(invoices, { query: 'Waiting for client' }).length, 1);
  assert.deepEqual(filterInvoices(invoices), invoices);
  assert.notEqual(filterInvoices(invoices), invoices);
  assert.deepEqual(filterInvoices(invoices, { status: 'unsupported' }), []);
  assert.deepEqual(filterInvoices(invoices, { query: 'missing supplier' }), []);
  assert.deepEqual(summarizeInvoices([]), { completed: 0, waiting_for_client: 0, blocked: 0, received: 0, in_review: 0, attention: 0 });
  assert.deepEqual(summarizeInvoices(invoices), { completed: 2, waiting_for_client: 1, blocked: 1, received: 0, in_review: 0, attention: 0 });
  assert.deepEqual(Object.keys(STATUS_LABELS), ['completed', 'waiting_for_client', 'blocked', 'received', 'in_review', 'attention']);
});

test('validation rejects incomplete, wrong-type, oversized and unsupported usage answers', () => {
  const invalid = [null, undefined, {}, '',
    { ...reply, vehicleRegistration: '   ' }, { ...reply, vehicleRegistration: 123 },
    { ...reply, vehicleRegistration: 'x'.repeat(33) },
    { ...reply, purpose: '\n\t' }, { ...reply, purpose: {} },
    { ...reply, purpose: 'x'.repeat(1001) },
    { ...reply, usage: 'private' }, { ...reply, usage: 'BUSINESS' },
  ];
  const invoices = freezeDeep(createDemoInvoices());
  for (const answer of invalid) {
    assert.ok(Object.keys(validateDemoAnswer(answer)).length > 0);
    assert.throws(() => resolveDemoQuestion(invoices, 'DEMO-003', answer));
  }
  assert.deepEqual(validateDemoAnswer(reply), {});
  assert.deepEqual(validateDemoAnswer({ ...reply, usage: 'business' }), {});
  assert.deepEqual(validateDemoAnswer({ ...reply, vehicleRegistration: 'x'.repeat(32), purpose: 'x'.repeat(1000) }), {});
});

test('resolution changes only the requested case without mutating input or retaining the reply object', () => {
  const invoices = freezeDeep(createDemoInvoices());
  const answer = { ...reply };
  const result = resolveDemoQuestion(invoices, 'DEMO-003', answer);
  assert.notEqual(result, invoices);
  assert.equal(invoices[2].status, 'waiting_for_client');
  assert.equal(invoices[2].answer, null);
  assert.equal(invoices[2].timeline.length, 2);
  assert.equal(result[2].status, 'completed');
  assert.deepEqual(result[2].answer, { vehicleRegistration: 'DEMO 123', usage: 'mixed', purpose: 'Client visit' });
  answer.purpose = 'changed later';
  assert.equal(result[2].answer.purpose, 'Client visit');
  for (const index of [0, 1, 3]) assert.deepEqual(result[index], invoices[index]);
  assert.equal(result[2].question, invoices[2].question);
  assert.equal(result[2].precedentId, null);
  assert.equal(result[2].timeline.length, 4);
  assert.match(result[2].reasoning, /Synthetic decision/);
  assert.deepEqual(summarizeInvoices(result), { completed: 3, waiting_for_client: 0, blocked: 1, received: 0, in_review: 0, attention: 0 });
  assert.deepEqual(resolveDemoQuestion(invoices, 'DEMO-003', reply), result, 'same input produces deterministic output');
});

test('retries, completed cases, blocked cases and unknown IDs cannot create another decision', () => {
  const original = createDemoInvoices();
  const resolved = freezeDeep(resolveDemoQuestion(original, 'DEMO-003', reply));
  const snapshot = JSON.stringify(resolved);
  for (const id of ['DEMO-001', 'DEMO-002', 'DEMO-003', 'DEMO-004', 'UNKNOWN']) {
    assert.throws(() => resolveDemoQuestion(resolved, id, reply));
  }
  assert.equal(JSON.stringify(resolved), snapshot);
  assert.equal(resolved[2].timeline.filter(event => event.title === 'Synthetic decision').length, 1);
});

// Parse CSV independently so round-trip assertions also cover embedded line breaks and quotes.
function parseCsv(text) {
  const rows = [];
  let row = [], field = '', quoted = false;
  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    if (char === '"') {
      if (quoted && text[i + 1] === '"') { field += '"'; i++; }
      else quoted = !quoted;
    } else if (!quoted && char === ',') { row.push(field); field = ''; }
    else if (!quoted && char === '\r' && text[i + 1] === '\n') {
      row.push(field); rows.push(row); row = []; field = ''; i++;
    } else field += char;
  }
  assert.equal(quoted, false);
  return rows;
}

test('CSV preserves commas, quotes, multiline content and Unicode while marking demo origin', () => {
  const invoices = createDemoInvoices();
  invoices[0].supplier = 'Supplier, "A"\r\nWrocław';
  invoices[0].answer = { vehicleRegistration: 'DEMO 123', usage: 'mixed', purpose: 'Visit, "client"\nReturn' };
  const csv = exportInvoicesCsv(freezeDeep(invoices));
  const rows = parseCsv(csv);
  assert.equal(rows.length, 5);
  assert.ok(rows.every(row => row.length === rows[0].length));
  assert.equal(rows[1][1], invoices[0].supplier);
  assert.equal(rows[1][10], invoices[0].answer.purpose);
  assert.equal(rows[1][3], '615.00');
  assert.equal(rows[1][13], 'Synthetic demo only');
  assert.equal(rows[3][8], '');
  assert.equal(parseCsv(exportInvoicesCsv([])).length, 1);
});

test('CSV neutralizes spreadsheet formula injection across invoice and client-answer fields', () => {
  const payloads = ['=HYPERLINK("https://example.test")', '+SUM(1,2)', '-1+2', '@SUM(1,2)',
    '   =1+1', '\t=1+1', '\r\n+1', '\u0000=1+1', '\ttext'];
  for (const payload of payloads) {
    const invoices = createDemoInvoices();
    Object.assign(invoices[0], {
      id: payload, supplier: payload, context: payload, reasoning: payload, precedentId: payload,
      answer: { vehicleRegistration: payload, usage: payload, purpose: payload },
    });
    const row = parseCsv(exportInvoicesCsv(invoices))[1];
    for (const column of [0, 1, 7, 8, 9, 10, 11, 12]) assert.equal(row[column], `'${payload}`);
  }
});


test('platform attention counts and filters include only received and in-review invoices', () => {
  const invoices = freezeDeep(['received', 'in_review', 'waiting_for_client', 'completed', 'blocked'].map((status, index) => ({
    id: `API-${index + 1}`, status, origin: 'platform', supplier: index === 0 ? 'First seller' : 'Other seller',
  })));
  assert.deepEqual(summarizeInvoices(invoices), { completed: 1, waiting_for_client: 1, blocked: 1, received: 1, in_review: 1, attention: 2 });
  assert.deepEqual(filterInvoices(invoices, { status: 'attention' }).map(row => row.id), ['API-1', 'API-2']);
  assert.deepEqual(filterInvoices(invoices, { status: 'attention', query: 'first' }).map(row => row.id), ['API-1']);
  assert.deepEqual(filterInvoices(invoices, { status: 'blocked' }).map(row => row.id), ['API-5']);
  assert.equal(filterInvoices(invoices, { query: 'In review' })[0].id, 'API-2');
  assert.equal(STATUS_LABELS.received, 'Received');
  assert.equal(STATUS_LABELS.in_review, 'In review');
});

test('API invoice CSV needs no synthetic answer, source, reasoning or timeline fields', () => {
  const invoice = freezeDeep({
    id: 'API-23', origin: 'platform', supplier: 'Platform seller, "A"', date: '2026-11-05',
    amount: 246, netAmount: 200, vatAmount: 46, status: 'in_review', context: 'Recorded purchase',
    raw: { status: 'escalated', vehicle_plate: '=UNTRUSTED' },
    cases: [], questions: [],
  });
  const rows = parseCsv(exportInvoicesCsv([invoice, createDemoInvoices()[0]]));
  assert.equal(rows[1][0], 'API-23');
  assert.equal(rows[1][1], invoice.supplier);
  assert.equal(rows[1][3], '246.00');
  assert.equal(rows[1][6], 'In review');
  assert.equal(rows[1][8], "'=UNTRUSTED");
  assert.equal(rows[1][11], '');
  assert.equal(rows[1][12], '');
  assert.equal(rows[1][13], 'Platform API (demo records)');
  assert.equal(rows[2][13], 'Synthetic demo only');
});

test('synthetic resolution cannot modify a waiting platform invoice', () => {
  const invoices = freezeDeep([{ ...createDemoInvoices()[2], id: 'API-3', origin: 'platform' }]);
  assert.throws(() => resolveDemoQuestion(invoices, 'API-3', reply), /read only/);
  assert.equal(invoices[0].status, 'waiting_for_client');
});
