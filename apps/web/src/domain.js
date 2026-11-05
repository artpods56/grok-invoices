export const STATUS_LABELS = Object.freeze({
  completed: 'Completed',
  waiting_for_client: 'Waiting for client',
  blocked: 'Blocked',
  received: 'Received',
  in_review: 'In review',
  attention: 'Needs attention',
});

const reference = {
  title: 'Ministry of Finance · KSeF integrator documentation',
  url: 'https://ksef.podatki.gov.pl/ksef-na-okres-obligatoryjny/wsparcie-dla-integratorow/',
  note: 'Official reference only. No KSeF connection, invoice acceptance or legal applicability was verified by this demo.',
};
const vatReference = {
  title: 'ELI · VAT Act reference',
  url: 'https://eli.gov.pl/eli/DU/2004/535/ogl',
  note: 'Official reference only. No current provision or vehicle tax treatment was verified by this demo.',
};

// These are authored fixtures, not imported invoices or external audit events.
const fixtures = [
  {
    id: 'DEMO-001', supplier: 'Demo IT Services', initials: 'DI',
    date: '2026-11-05', amount: 615, netAmount: 500, vatAmount: 115,
    status: 'completed', context: 'IT services', question: null, answer: null,
    reasoning: 'Synthetic decision: the IT services fixture is marked complete to demonstrate the inspection workflow. No posting or tax calculation was performed.',
    sources: [reference], precedentId: null,
    timeline: [
      { time: 'Demo step 1', title: 'Fixture loaded', description: 'Authored IT services example; no external import.' },
      { time: 'Demo step 2', title: 'Synthetic decision', description: 'Seeded as completed for the demo; no legal verification.' },
    ],
  },
  {
    id: 'DEMO-002', supplier: 'Demo Fuel Station', initials: 'DF',
    date: '2026-11-05', amount: 246, netAmount: 200, vatAmount: 46,
    status: 'completed', context: 'Known vehicle', question: null, answer: null,
    reasoning: 'Synthetic decision: this fixture assumes matching vehicle context and a demo precedent. Supplier identity alone is not a valid match. No deductible VAT or expense treatment was determined.',
    sources: [vatReference, reference], precedentId: 'DEMO-PRECEDENT-001',
    timeline: [
      { time: 'Demo step 1', title: 'Fixture loaded', description: 'Authored fuel invoice for a known demo vehicle.' },
      { time: 'Demo step 2', title: 'Demo precedent referenced', description: 'Seeded context match, not a verified policy or legal decision.' },
    ],
  },
  {
    id: 'DEMO-003', supplier: 'Demo Fuel Station', initials: 'DF',
    date: '2026-11-05', amount: 246, netAmount: 200, vatAmount: 46,
    status: 'waiting_for_client', context: 'Unknown vehicle',
    question: 'Which vehicle does this fuel purchase concern, how is it used, and what was the business purpose?',
    answer: null,
    reasoning: 'Vehicle registration, usage and purchase purpose are missing. The demo waits for all three facts before recording a synthetic completion. No tax treatment is inferred from the supplier.',
    sources: [vatReference, reference], precedentId: null,
    timeline: [
      { time: 'Demo step 1', title: 'Fixture loaded', description: 'Synthetic fuel invoice: net PLN 200.00, VAT PLN 46.00, gross PLN 246.00.' },
      { time: 'Demo step 2', title: 'Context requested', description: 'Question prepared in local demo state. No phone call or Grok Bot message was sent.' },
    ],
  },
  {
    id: 'DEMO-004', supplier: 'Demo Supplier', initials: 'DS',
    date: '2026-11-05', amount: 123, netAmount: 100, vatAmount: 23,
    status: 'blocked', context: 'Missing context', question: null, answer: null,
    reasoning: 'Synthetic block: the fixture has insufficient purchase details and company policy context. A vehicle reply cannot resolve this case. No accounting or legal conclusion is available.',
    sources: [reference], precedentId: null,
    timeline: [
      { time: 'Demo step 1', title: 'Fixture loaded', description: 'Authored example with missing purchase context.' },
      { time: 'Demo step 2', title: 'Blocked', description: 'Insufficient evidence; no reusable precedent created.' },
    ],
  },
];

export function createDemoInvoices() {
  return fixtures.map(invoice => structuredClone(invoice));
}

export function summarizeInvoices(invoices) {
  return invoices.reduce((counts, invoice) => {
    if (Object.hasOwn(counts, invoice.status)) counts[invoice.status] += 1;
    if (['received', 'in_review'].includes(invoice.status)) counts.attention += 1;
    return counts;
  }, { completed: 0, waiting_for_client: 0, blocked: 0, received: 0, in_review: 0, attention: 0 });
}

export function filterInvoices(invoices, { query = '', status = 'all' } = {}) {
  const search = String(query ?? '').trim().toLowerCase();
  return invoices.filter(invoice =>
    (!status || status === 'all' || invoice.status === status || (status === 'attention' && ['received', 'in_review'].includes(invoice.status))) &&
    [invoice.id, invoice.supplier, invoice.context, invoice.date, STATUS_LABELS[invoice.status]]
      .some(value => String(value ?? '').toLowerCase().includes(search)),
  );
}

export function validateDemoAnswer(answer) {
  const errors = {};
  if (typeof answer?.vehicleRegistration !== 'string' || !answer.vehicleRegistration.trim()) {
    errors.vehicleRegistration = 'Enter the vehicle registration.';
  } else if (answer.vehicleRegistration.trim().length > 32) {
    errors.vehicleRegistration = 'Use at most 32 characters.';
  }
  if (!['mixed', 'business'].includes(answer?.usage)) {
    errors.usage = 'Select mixed or business use.';
  }
  if (typeof answer?.purpose !== 'string' || !answer.purpose.trim()) {
    errors.purpose = 'Describe the business purpose.';
  } else if (answer.purpose.trim().length > 1000) {
    errors.purpose = 'Use at most 1,000 characters.';
  }
  return errors;
}

export function resolveDemoQuestion(invoices, invoiceId, answer) {
  const invoice = invoices.find(item => item.id === invoiceId);
  if (!invoice) throw new Error('Invoice not found.');
  if (invoice.origin === 'platform') throw new Error('Platform invoices are read only.');
  if (invoice.status !== 'waiting_for_client') {
    throw new Error('Only cases waiting for the client can be resolved.');
  }
  const errors = validateDemoAnswer(answer);
  if (Object.keys(errors).length) throw new Error(Object.values(errors).join(' '));
  const normalized = {
    vehicleRegistration: answer.vehicleRegistration.trim().toUpperCase(),
    usage: answer.usage,
    purpose: answer.purpose.trim(),
  };
  return invoices.map(item => item.id !== invoiceId ? item : {
    ...item,
    status: 'completed',
    context: 'Vehicle context supplied',
    answer: normalized,
    reasoning: 'Synthetic decision: the supplied vehicle facts complete this local demo workflow. This is not a tax, deductibility or accounting conclusion. No external verification, posting or reusable legal precedent was created.',
    timeline: [...item.timeline,
      { time: 'Demo step 3', title: 'Demo answer recorded', description: 'Vehicle registration, usage and purpose supplied in this browser session.' },
      { time: 'Demo step 4', title: 'Synthetic decision', description: 'Local demo marked complete; no live integration or tax calculation.' },
    ],
  });
}

function csvCell(value) {
  let text = String(value ?? '');
  // Quote CSV syntax and neutralize spreadsheet formulas, including whitespace/control prefixes.
  if (/^[\s\u0000-\u001f]*[=+\-@]/u.test(text) || /^[\t\r\n]/u.test(text)) text = `'${text}`;
  return `"${text.replaceAll('"', '""')}"`;
}

export function exportInvoicesCsv(invoices) {
  const rows = [
    ['Invoice ID', 'Supplier', 'Date', 'Gross PLN', 'Net PLN', 'VAT PLN', 'Status', 'Context', 'Vehicle registration', 'Usage', 'Purpose', 'Reasoning', 'Precedent ID', 'Data origin'],
    ...invoices.map(invoice => [
      invoice.id, invoice.supplier, invoice.date, invoice.amount.toFixed(2),
      invoice.netAmount.toFixed(2), invoice.vatAmount.toFixed(2), STATUS_LABELS[invoice.status],
      invoice.context, invoice.answer?.vehicleRegistration ?? invoice.raw?.vehicle_plate, invoice.answer?.usage,
      invoice.answer?.purpose, invoice.reasoning, invoice.precedentId,
      invoice.origin === 'platform' ? 'Platform API (demo records)' : 'Synthetic demo only',
    ]),
  ];
  return rows.map(row => row.map(csvCell).join(',')).join('\r\n') + '\r\n';
}
