import { useEffect, useId, useRef, useState } from 'react';
import { loadPlatformInvoice } from './platform.js';
import './platform-drawer.css';

const money = value => new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'PLN' }).format(Number(value));
const focusable = 'button:not(:disabled), a[href], [tabindex="0"]';

export function PlatformDrawer({ invoice, onClose }) {
  return invoice ? <PlatformDetails key={invoice.apiId ?? invoice.id} invoice={invoice} onClose={onClose} /> : null;
}

function PlatformDetails({ invoice, onClose }) {
  const titleId = useId();
  const dialog = useRef(null);
  const closeButton = useRef(null);
  const closeCallback = useRef(onClose);
  closeCallback.current = onClose;
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setDetail(null); setError('');
    loadPlatformInvoice(invoice.apiId, { signal: controller.signal }).then(result => {
      if (active) setDetail(result);
    }).catch(failure => {
      if (active) setError(failure instanceof Error ? failure.message : 'Could not load platform invoice.');
    });
    return () => { active = false; controller.abort(); };
  }, [invoice.apiId, attempt]);

  useEffect(() => {
    const opener = document.activeElement;
    closeButton.current?.focus();
    function onKeyDown(event) {
      if (event.key === 'Escape') {
        event.preventDefault(); event.stopPropagation(); closeCallback.current();
      }
      if (event.key !== 'Tab') return;
      const controls = [...dialog.current.querySelectorAll(focusable)].filter(item => item.getClientRects().length && item.tabIndex >= 0);
      const first = controls[0]; const last = controls[controls.length - 1];
      if (!first) { event.preventDefault(); dialog.current.focus(); }
      else if (event.shiftKey && (document.activeElement === first || !controls.includes(document.activeElement))) {
        event.preventDefault(); last.focus();
      } else if (!event.shiftKey && (document.activeElement === last || !controls.includes(document.activeElement))) {
        event.preventDefault(); first.focus();
      }
    }
    function containFocus(event) {
      if (!dialog.current.contains(event.target)) closeButton.current?.focus();
    }
    document.addEventListener('keydown', onKeyDown, true);
    document.addEventListener('focusin', containFocus);
    return () => {
      document.removeEventListener('keydown', onKeyDown, true);
      document.removeEventListener('focusin', containFocus);
      if (opener instanceof HTMLElement && opener.isConnected) opener.focus();
    };
  }, []);

  return <div className="platform-overlay" onClick={event => { if (event.target === event.currentTarget) onClose(); }}>
    <aside className="platform-drawer" role="dialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={`${titleId}-notice`} tabIndex={-1} ref={dialog}>
      <header className="platform-header">
        <div><p className="platform-eyebrow">Platform invoice · read only</p><h2 id={titleId}>{invoice.id}</h2></div>
        <button type="button" ref={closeButton} onClick={onClose} aria-label="Close platform invoice details">Close <span aria-hidden="true">×</span></button>
      </header>
      <div className="platform-content">
        <p className="platform-notice" id={`${titleId}-notice`}>Mock-backed platform demo. This view reads server records; it does not connect to live KSeF or submit changes.</p>
        {!detail && !error && <p role="status">Loading platform invoice…</p>}
        {error && <div><p className="platform-error" role="alert">{error}</p><button type="button" onClick={() => setAttempt(value => value + 1)}>Retry loading</button></div>}
        {detail && <>
          <section className="platform-section" aria-label="Invoice">
            <h3>{detail.supplier}</h3>
            <dl className="platform-facts">
              <Fact label="Platform invoice state" value={detail.raw.status} />
              <Fact label="Dashboard state" value={detail.status} />
              <Fact label="KSeF reference (demo)" value={detail.raw.ksef_number} />
              <Fact label="Seller NIP" value={detail.raw.seller_nip} />
              <Fact label="Issue date" value={detail.date} />
              <Fact label="Received at" value={detail.raw.received_at} />
              <Fact label="Net amount" value={money(detail.netAmount)} />
              <Fact label="Invoice VAT" value={money(detail.vatAmount)} />
              <Fact label="Gross amount" value={money(detail.amount)} />
              <Fact label="Vehicle registration" value={detail.raw.vehicle_plate ?? 'Not supplied'} />
            </dl>
            <p>{detail.context}</p>
          </section>
          <section className="platform-section" aria-label="Cases and client answers">
            <h3>Cases and client answers</h3>
            {!detail.cases.length && <p className="platform-muted">No cases recorded.</p>}
            {detail.cases.map(item => <article className="platform-record" key={item.id}>
              <h4>Case #{item.id} · {item.status}</h4><p>{item.reason}</p>
              <p className="platform-muted">Opened by {item.opened_by} · Assignee: {item.assignee ?? 'Unassigned'}</p>
              {!item.questions.length && <p className="platform-muted">No questions recorded.</p>}
              {item.questions.map(question => <div className="platform-question" key={question.id}>
                <h4>Question #{question.id} · {question.status}</h4><p>{question.text}</p>
                <p className="platform-muted">Asked by {question.asked_by} · {question.created_at}</p>
                <p><strong>Recorded answer: </strong>{question.answer ?? 'No answer recorded.'}</p>
                {question.answered_at && <p className="platform-muted">Answered by {question.answered_by ?? 'Not recorded'} · {question.answered_at}</p>}
              </div>)}
            </article>)}
          </section>
          <section className="platform-section" aria-label="Postings">
            <h3>Postings</h3>
            {!detail.postings.length && <p className="platform-muted">No postings recorded.</p>}
            {detail.postings.map(posting => <article className="platform-record" key={posting.id}>
              <h4>Posting #{posting.id} · {posting.status}</h4>
              <dl className="platform-facts">
                <Fact label="Account" value={posting.account} />
                <Fact label="Source / actor" value={`${posting.source} / ${posting.actor}`} />
                <Fact label="VAT deduction" value={`${posting.vat_deduction_percent}%`} />
                <Fact label="Deductible VAT" value={money(posting.deductible_vat)} />
                <Fact label="Precedent reference" value={posting.precedent_id == null ? 'None recorded' : `#${posting.precedent_id}`} />
                <Fact label="Recorded at" value={posting.created_at} />
              </dl>
              <p>{posting.rationale}</p><p><strong>Recorded legal basis: </strong>{posting.legal_basis ?? 'None recorded.'}</p>
            </article>)}
          </section>
          <section className="platform-section" aria-label="Platform timeline">
            <h3>Platform timeline</h3><p className="platform-muted">Matching events in the API window (up to 200 platform events). Earlier or later records may be outside this window.</p>
            {!detail.events.length && <p>No matching events in this window.</p>}
            <ol className="platform-timeline">{detail.events.map(event => <li key={event.id}>
              <time>{event.at}</time><h4>{event.type} · {event.actor}</h4><p>{event.summary}</p>
            </li>)}</ol>
          </section>
        </>}
      </div>
    </aside>
  </div>;
}

function Fact({ label, value }) {
  return <div><dt>{label}</dt><dd>{value}</dd></div>;
}
