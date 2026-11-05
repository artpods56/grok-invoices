import test from 'node:test';
import assert from 'node:assert/strict';
import { STATUS_LABELS, summarizeInvoices, filterInvoices, exportInvoicesCsv } from '../src/domain.js';

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

const invoice = (id, status, extra = {}) => ({
  id, status, supplier: 'Other seller', context: 'Recorded purchase', date: '2026-11-05',
  amount: 246, netAmount: 200, vatAmount: 46, origin: 'platform', raw: { vehicle_plate: null }, ...extra,
});

test('attention counts and filters include only received and in-review invoices', () => {
  const invoices = Object.freeze(['received', 'in_review', 'waiting_for_client', 'completed'].map((status, index) =>
    invoice(`API-${index + 1}`, status, index === 0 ? { supplier: 'First seller' } : {})));
  assert.deepEqual(summarizeInvoices([]), { completed: 0, waiting_for_client: 0, received: 0, in_review: 0, attention: 0 });
  assert.deepEqual(summarizeInvoices(invoices), { completed: 1, waiting_for_client: 1, received: 1, in_review: 1, attention: 2 });
  assert.deepEqual(filterInvoices(invoices, { status: 'attention' }).map(row => row.id), ['API-1', 'API-2']);
  assert.deepEqual(filterInvoices(invoices, { status: 'attention', query: ' FIRST ' }).map(row => row.id), ['API-1']);
  assert.equal(filterInvoices(invoices, { query: 'In review' })[0].id, 'API-2');
  assert.deepEqual(filterInvoices(invoices), [...invoices]);
  assert.deepEqual(filterInvoices(invoices, { query: 'missing supplier' }), []);
  assert.equal(STATUS_LABELS.attention, 'Needs attention');
});

test('CSV preserves commas, quotes, multiline content and Unicode', () => {
  const row = invoice('API-23', 'in_review', { supplier: 'Seller, "A"\r\nWrocław', raw: { vehicle_plate: 'GD 9R247' } });
  const rows = parseCsv(exportInvoicesCsv([row]));
  assert.equal(rows.length, 2);
  assert.ok(rows.every(cells => cells.length === rows[0].length));
  assert.equal(rows[1][1], row.supplier);
  assert.equal(rows[1][3], '246.00');
  assert.equal(rows[1][6], 'In review');
  assert.equal(rows[1][8], 'GD 9R247');
  assert.equal(parseCsv(exportInvoicesCsv([])).length, 1);
});

test('CSV neutralizes spreadsheet formula injection', () => {
  for (const payload of ['=HYPERLINK("https://example.test")', '+SUM(1,2)', '-1+2', '@SUM(1,2)', '   =1+1', '\t=1+1', '\r\n+1', '\u0000=1+1', '\ttext']) {
    const row = parseCsv(exportInvoicesCsv([invoice(payload, 'completed', { supplier: payload, context: payload, raw: { vehicle_plate: payload } })]))[1];
    for (const column of [0, 1, 7, 8]) assert.equal(row[column], `'${payload}`);
  }
});
