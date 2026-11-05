// Read-only projections of the platform API. The server remains the source of truth.
function invalid(path, field) {
  throw new Error(`Invalid platform response from ${path}: ${field}.`);
}

function object(value, path) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) invalid(path, 'expected an object');
  return value;
}

function text(value, path, field) {
  if (typeof value !== 'string' || !value.trim()) invalid(path, field);
}

function id(value, path, field = 'id') {
  if (!Number.isSafeInteger(value) || value < 1) invalid(path, field);
}

function enumeration(value, values, path, field) {
  if (!values.includes(value)) invalid(path, field);
}

function decimal(value, path, field) {
  if (!['number', 'string'].includes(typeof value) || !/^\d+(?:\.\d{1,2})?$/.test(String(value)) ||
      !Number.isFinite(Number(value)) || Number(value) * 100 > Number.MAX_SAFE_INTEGER) invalid(path, field);
  return Number(value);
}

function rows(value, path, validate) {
  if (!Array.isArray(value)) invalid(path, 'expected an array');
  const seen = new Set();
  value.forEach(row => {
    object(row, path);
    validate(row, path);
    if (seen.has(row.id)) invalid(path, 'duplicate id');
    seen.add(row.id);
  });
  return value;
}

function invoiceRow(row, path) {
  object(row, path);
  id(row.id, path);
  for (const field of ['seller_name', 'seller_nip', 'description', 'ksef_number', 'issue_date', 'received_at']) text(row[field], path, field);
  enumeration(row.status, ['received', 'escalated', 'posted'], path, 'status');
  for (const field of ['net', 'vat', 'gross']) decimal(row[field], path, field);
  if (row.vehicle_plate !== null && typeof row.vehicle_plate !== 'string') invalid(path, 'vehicle_plate');
}

function caseRow(row, path) {
  id(row.id, path); id(row.invoice_id, path, 'invoice_id');
  enumeration(row.status, ['open', 'waiting_for_client', 'resolved'], path, 'status');
  text(row.reason, path, 'reason');
}

function questionRow(row, path) {
  id(row.id, path); id(row.case_id, path, 'case_id');
  text(row.text, path, 'text');
  enumeration(row.status, ['open', 'answered'], path, 'status');
  if (row.answer !== null && typeof row.answer !== 'string') invalid(path, 'answer');
  if (row.status === 'answered') text(row.answer, path, 'answer');
}

function eventRow(row, path) {
  id(row.id, path);
  for (const field of ['at', 'actor', 'type', 'summary']) text(row[field], path, field);
  if (row.invoice_id !== null) id(row.invoice_id, path, 'invoice_id');
  if (row.case_id !== null) id(row.case_id, path, 'case_id');
  object(row.data, path);
}

function postingRow(row, path) {
  id(row.id, path); id(row.invoice_id, path, 'invoice_id');
  for (const field of ['account', 'rationale', 'actor', 'created_at']) text(row[field], path, field);
  enumeration(row.status, ['active', 'superseded'], path, 'posting status');
  enumeration(row.source, ['rule', 'precedent', 'regulation', 'accountant'], path, 'posting source');
  decimal(row.deductible_vat, path, 'deductible_vat');
  if (!Number.isInteger(row.vat_deduction_percent) || row.vat_deduction_percent < 0 || row.vat_deduction_percent > 100) invalid(path, 'vat_deduction_percent');
  if (row.legal_basis !== null && typeof row.legal_basis !== 'string') invalid(path, 'legal_basis');
}

async function get(path, signal) {
  const response = await fetch(`/api${path}`, { method: 'GET', signal, headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error(`Platform GET /api${path} failed (HTTP ${response.status}).`);
  try { return await response.json(); }
  catch (error) {
    if (error?.name === 'AbortError') throw error;
    throw new Error(`Invalid JSON from /api${path}.`, { cause: error });
  }
}

function normalize(row, cases, questions) {
  const relatedCases = cases.filter(item => item.invoice_id === row.id);
  const caseIds = new Set(relatedCases.map(item => item.id));
  const relatedQuestions = questions.filter(item => caseIds.has(item.case_id));
  let status = row.status === 'posted' ? 'completed' : row.status === 'received' ? 'received' : 'in_review';
  if (row.status !== 'posted') {
    if (relatedCases.some(item => item.status === 'waiting_for_client')) status = 'waiting_for_client';
    else if (relatedCases.some(item => item.status === 'open')) status = 'in_review';
  }
  return {
    id: `API-${row.id}`, apiId: row.id, supplier: row.seller_name,
    initials: row.seller_name.trim().split(/\s+/).slice(0, 2).map(word => Array.from(word)[0]).join('').toUpperCase(),
    date: row.issue_date, amount: Number(row.gross), netAmount: Number(row.net), vatAmount: Number(row.vat),
    status, context: row.description, origin: 'platform', raw: row,
    cases: relatedCases, questions: relatedQuestions,
  };
}

export async function loadPlatformSnapshot({ signal } = {}) {
  const [invoices, cases, questions, client, events] = await Promise.all(
    ['/invoices', '/cases', '/questions', '/client', '/events'].map(path => get(path, signal)),
  );
  rows(invoices, '/invoices', invoiceRow);
  rows(cases, '/cases', caseRow);
  rows(questions, '/questions', questionRow);
  rows(events, '/events', eventRow);
  object(client, '/client');
  text(client.name, '/client', 'name'); text(client.nip, '/client', 'nip');
  if (!Array.isArray(client.fleet) || !Array.isArray(client.facts)) invalid('/client', 'fleet or facts');
  return { invoices: invoices.map(row => normalize(row, cases, questions)), client, events };
}

// The API has no list of postings, so decisions and precedents come from each invoice's detail.
export async function loadPlatformPostings(invoices, { signal } = {}) {
  const details = await Promise.all(invoices.map(invoice => get(`/invoices/${invoice.apiId}`, signal)));
  return details.flatMap((detail, index) => {
    const path = `/invoices/${invoices[index].apiId}`;
    object(detail, path);
    return rows(detail.postings, path, postingRow);
  });
}

// Returns a fresh normalized invoice plus real case questions, postings and matching events.
// /events is the server's bounded event window (200 by default), not a full audit export.
export async function loadPlatformInvoice(apiId, { signal } = {}) {
  id(apiId, '/invoices', 'apiId');
  const path = `/invoices/${apiId}`;
  const [raw, events] = await Promise.all([get(path, signal), get('/events', signal)]);
  invoiceRow(raw, path);
  if (raw.id !== apiId) invalid(path, 'invoice id mismatch');
  rows(raw.cases, path, caseRow); rows(raw.postings, path, postingRow);
  if (raw.cases.some(item => item.invoice_id !== apiId) || raw.postings.some(item => item.invoice_id !== apiId)) invalid(path, 'invoice relation mismatch');
  rows(events, '/events', eventRow);
  const cases = await Promise.all(raw.cases.map(async item => {
    const casePath = `/cases/${item.id}`;
    const detail = object(await get(casePath, signal), casePath);
    caseRow(detail, casePath);
    invoiceRow(detail.invoice, casePath);
    if (detail.id !== item.id || detail.invoice_id !== apiId || detail.invoice.id !== apiId) invalid(casePath, 'case relation mismatch');
    rows(detail.questions, casePath, questionRow);
    if (detail.questions.some(question => question.case_id !== item.id)) invalid(casePath, 'question relation mismatch');
    return detail;
  }));
  const caseIds = new Set(cases.map(item => item.id));
  return {
    ...normalize(raw, cases, cases.flatMap(item => item.questions)),
    postings: raw.postings,
    events: events.filter(event => event.invoice_id === apiId || caseIds.has(event.case_id)),
  };
}
