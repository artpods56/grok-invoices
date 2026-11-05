import { STATUS_LABELS } from './domain.js';

const roles = [
  ['Invoice agent', 'invoice_agent', 'Invoice intake and case escalation'],
  ['Regulations agent', 'regulations_agent', 'Recorded accounting rationale and questions'],
  ['Client agent', 'client_agent', 'Client answers and context'],
];

function conditionsLabel(conditions) {
  const parts = [];
  if (conditions?.vehicle_usage) parts.push(`vehicle usage ${conditions.vehicle_usage}`);
  if (conditions?.vehicle_plate) parts.push(`vehicle ${conditions.vehicle_plate}`);
  return parts.length ? `Applies when: ${parts.join(', ')}` : 'No conditions';
}

export function PlatformSections({ page, invoices, snapshot, onInspect }) {
  const inspect = invoice => <button className="text-button" onClick={() => onInspect(invoice.id)}>Inspect {invoice.id} →</button>;
  const questions = invoices.flatMap(invoice => invoice.questions.map(question => ({ invoice, question })));
  if (page === 'Questions') return <>
    {questions.map(({ invoice, question }) => <article className="detail-row" key={question.id}>
      <div><h3>{question.text}</h3><p>{question.status} · Case #{question.case_id}</p><p><strong>Recorded answer: </strong>{question.answer ?? 'No answer recorded.'}</p></div>{inspect(invoice)}
    </article>)}
    {!questions.length && <p className="panel-empty">No recorded questions in these results.</p>}
  </>;
  if (page === 'Company context') return snapshot?.client ? <div className="context-content">
    <h3>{snapshot.client.name}</h3><p>NIP: {snapshot.client.nip} · Platform demo company</p>
    <h3>Fleet</h3>{snapshot.client.fleet.map((vehicle, index) => <article className="detail-row" key={index}><div><h3>{vehicle.plate}</h3><p>{vehicle.model} · {vehicle.usage}</p></div></article>)}
    {!snapshot.client.fleet.length && <p>No vehicles recorded.</p>}
    <h3>Recorded facts</h3>{snapshot.client.facts.map(fact => <article className="detail-row" key={fact.id}><div><h3>{fact.key}</h3><p>{fact.value}</p><p className="muted">{fact.source} · {fact.created_at}</p></div></article>)}
    {!snapshot.client.facts.length && <p>No client facts recorded.</p>}
  </div> : <p className="panel-empty">Company context is unavailable until the platform loads.</p>;
  if (page === 'Agents') return <>
    {roles.map(([name, actor, description]) => {
      const events = snapshot?.events.filter(event => event.actor === actor) ?? [];
      return <article className="detail-row" key={actor}><div><h3>{name}</h3><p>{description}</p><p>{events.length} recorded event(s) in the current API window.</p></div><span className="neutral-badge">Platform role</span></article>;
    })}
    <p className="panel-note">Roles and recorded activity do not indicate that an agent is currently running. This dashboard reads records only.</p>
  </>;
  if (page === 'Activity') {
    const ids = new Set(invoices.map(invoice => invoice.apiId));
    const caseIds = new Set(invoices.flatMap(invoice => invoice.cases.map(item => item.id)));
    const events = snapshot?.events.filter(event => (event.invoice_id == null && event.case_id == null) || ids.has(event.invoice_id) || caseIds.has(event.case_id)) ?? [];
    return <><p className="panel-note">Current API window, up to 200 events. This is not a full audit history. Workspace events are included.</p>
      {events.map(event => <article className="detail-row" key={event.id}><div><h3>{event.type} · {event.actor}</h3><p>{event.summary}</p><time className="muted">{event.at}</time></div>{invoices.find(invoice => invoice.apiId === event.invoice_id) && inspect(invoices.find(invoice => invoice.apiId === event.invoice_id))}</article>)}
      {!events.length && <p className="panel-empty">No events in this window.</p>}
    </>;
  }
  if (snapshot?.postingsError && ['Decisions', 'Sources', 'Precedents'].includes(page)) {
    return <p className="panel-empty" role="alert">{snapshot.postingsError} Use Refresh above to retry.</p>;
  }
  const invoiceById = new Map(invoices.map(invoice => [invoice.apiId, invoice]));
  const postings = (snapshot?.postings ?? []).filter(posting => invoiceById.has(posting.invoice_id));
  const treatment = posting => `Account ${posting.account} · ${posting.vat_deduction_percent}% VAT deduction (PLN ${posting.deductible_vat})`;
  const about = posting => `${invoiceById.get(posting.invoice_id).supplier} · ${invoiceById.get(posting.invoice_id).context}`;
  if (page === 'Decisions') return <>
    {postings.map(posting => <article className="detail-row" key={posting.id}>
      <div><h3>{treatment(posting)}</h3><p>{about(posting)}</p><p>{posting.rationale}</p><p className="muted">{posting.source} · {posting.actor} · {posting.status}{posting.legal_basis ? ` · ${posting.legal_basis}` : ''}</p></div>{inspect(invoiceById.get(posting.invoice_id))}
    </article>)}
    {!postings.length && <p className="panel-empty">No decisions recorded in these results.</p>}
  </>;
  if (page === 'Precedents') {
    const precedents = postings.filter(posting => posting.reusable === true && posting.status === 'active');
    return <>
      {precedents.map(posting => <article className="detail-row" key={posting.id}>
        <div><h3>Precedent #{posting.id}: {treatment(posting)}</h3><p>{about(posting)}</p><p>{posting.rationale}</p><p className="muted">{conditionsLabel(posting.conditions)}</p></div>{inspect(invoiceById.get(posting.invoice_id))}
      </article>)}
      {!precedents.length && <p className="panel-empty">No precedents recorded in these results.</p>}
    </>;
  }
  if (page === 'Sources') {
    const cited = [...new Set(postings.map(posting => posting.legal_basis).filter(Boolean))];
    return <>
      <p className="panel-note">Legal bases cited in recorded decisions. The platform stores these as written and does not validate them.</p>
      {cited.map(basis => <article className="detail-row" key={basis}>
        <div><h3>{basis}</h3><p>Cited by {postings.filter(posting => posting.legal_basis === basis).map(posting => `decision #${posting.id}`).join(', ')}</p></div>
      </article>)}
      {!cited.length && <p className="panel-empty">No legal bases cited in these results.</p>}
    </>;
  }
  return null;
}
