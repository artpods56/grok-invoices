import { STATUS_LABELS } from './domain.js';

const roles = [
  ['Invoice agent', 'invoice_agent', 'Invoice intake and case escalation'],
  ['Regulations agent', 'regulations_agent', 'Recorded accounting rationale and questions'],
  ['Client agent', 'client_agent', 'Client answers and context'],
];

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
  if (['Sources', 'Precedents', 'Decisions'].includes(page)) return <>
    <p className="panel-note">{page === 'Decisions' ? 'Inspect an invoice for recorded postings and rationale.' : page === 'Sources' ? 'The invoice list does not include legal bases. Inspect invoice postings to read the recorded source and legal basis.' : 'The invoice list does not include precedent details. Inspect invoice postings for recorded precedent references.'} No applicability or legal verification is implied.</p>
    {invoices.map(invoice => <article className="detail-row" key={invoice.id}><div><h3>{invoice.supplier}</h3><p>{STATUS_LABELS[invoice.status]} · {invoice.context}</p>{invoice.cases.map(item => <p key={item.id}>Case #{item.id} · {item.status}: {item.reason}</p>)}</div>{inspect(invoice)}</article>)}
    {!invoices.length && <p className="panel-empty">No invoices in these results.</p>}
  </>;
  return null;
}
