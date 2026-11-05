export const STATUS_LABELS = Object.freeze({
  completed: 'Completed',
  waiting_for_client: 'Waiting for client',
  received: 'Received',
  in_review: 'In review',
  attention: 'Needs attention',
});

export function summarizeInvoices(invoices) {
  return invoices.reduce((counts, invoice) => {
    if (Object.hasOwn(counts, invoice.status)) counts[invoice.status] += 1;
    if (['received', 'in_review'].includes(invoice.status)) counts.attention += 1;
    return counts;
  }, { completed: 0, waiting_for_client: 0, received: 0, in_review: 0, attention: 0 });
}

export function filterInvoices(invoices, { query = '', status = 'all' } = {}) {
  const search = String(query ?? '').trim().toLowerCase();
  return invoices.filter(invoice =>
    (!status || status === 'all' || invoice.status === status || (status === 'attention' && ['received', 'in_review'].includes(invoice.status))) &&
    [invoice.id, invoice.supplier, invoice.context, invoice.date, STATUS_LABELS[invoice.status]]
      .some(value => String(value ?? '').toLowerCase().includes(search)),
  );
}

function csvCell(value) {
  let text = String(value ?? '');
  // Quote CSV syntax and neutralize spreadsheet formulas, including whitespace/control prefixes.
  if (/^[\s\u0000-\u001f]*[=+\-@]/u.test(text) || /^[\t\r\n]/u.test(text)) text = `'${text}`;
  return `"${text.replaceAll('"', '""')}"`;
}

export function exportInvoicesCsv(invoices) {
  const rows = [
    ['Invoice ID', 'Supplier', 'Date', 'Gross PLN', 'Net PLN', 'VAT PLN', 'Status', 'Context', 'Vehicle registration'],
    ...invoices.map(invoice => [
      invoice.id, invoice.supplier, invoice.date, invoice.amount.toFixed(2),
      invoice.netAmount.toFixed(2), invoice.vatAmount.toFixed(2), STATUS_LABELS[invoice.status],
      invoice.context, invoice.raw?.vehicle_plate,
    ]),
  ];
  return rows.map(row => row.map(csvCell).join(',')).join('\r\n') + '\r\n';
}
