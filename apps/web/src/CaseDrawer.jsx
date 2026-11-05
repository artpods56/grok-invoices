import { useEffect, useId, useRef, useState } from 'react';
import { STATUS_LABELS, validateDemoAnswer } from './domain.js';
import './case-drawer.css';

const money = value => new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'PLN' }).format(value);
const focusableSelector = 'button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]';

export function CaseDrawer({ invoice, onClose, onResolve }) {
  return invoice ? <CaseDetails key={invoice.id} invoice={invoice} onClose={onClose} onResolve={onResolve} /> : null;
}

function CaseDetails({ invoice, onClose, onResolve }) {
  const id = useId();
  const dialog = useRef(null);
  const closeButton = useRef(null);
  const closeCallback = useRef(onClose);
  closeCallback.current = onClose;
  const submitted = useRef(false);
  const [pending, setPending] = useState(false);
  const [saved, setSaved] = useState(false);
  const [answer, setAnswer] = useState({ vehicleRegistration: '', usage: '', purpose: '' });
  const [errors, setErrors] = useState({});
  const [failure, setFailure] = useState('');

  useEffect(() => {
    const opener = document.activeElement;
    closeButton.current?.focus();
    const controls = () => [...dialog.current.querySelectorAll(focusableSelector)]
      .filter(element => element.getClientRects().length > 0 && element.tabIndex >= 0);
    function onKeyDown(event) {
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        closeCallback.current();
      }
      if (event.key === 'Tab') {
        const items = controls();
        const first = items[0];
        const last = items[items.length - 1];
        if (!first) { event.preventDefault(); dialog.current.focus(); return; }
        if (event.shiftKey && (document.activeElement === first || !items.includes(document.activeElement))) {
          event.preventDefault(); last.focus();
        } else if (!event.shiftKey && (document.activeElement === last || !items.includes(document.activeElement))) {
          event.preventDefault(); first.focus();
        }
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

  function update(field, value) {
    setAnswer(current => ({ ...current, [field]: value }));
    setErrors(current => ({ ...current, [field]: undefined }));
    setFailure('');
  }

  async function submit(event) {
    event.preventDefault();
    if (submitted.current || invoice.status !== 'waiting_for_client') return;
    const nextErrors = validateDemoAnswer(answer);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) {
      dialog.current.querySelector(`[name="${Object.keys(nextErrors)[0]}"]`)?.focus();
      return;
    }
    submitted.current = true;
    setPending(true);
    try {
      await onResolve(invoice.id, {
        vehicleRegistration: answer.vehicleRegistration.trim().toUpperCase(),
        usage: answer.usage,
        purpose: answer.purpose.trim(),
      });
      setSaved(true);
    } catch (error) {
      submitted.current = false;
      setPending(false);
      setFailure(error instanceof Error ? error.message : 'The demo answer could not be saved. Try again.');
    }
  }

  const fieldProps = field => ({
    id: `${id}-${field}`, name: field, required: true,
    disabled: pending,
    'aria-invalid': Boolean(errors[field]),
    'aria-describedby': errors[field] ? `${id}-${field}-error` : undefined,
  });
  const fieldError = field => errors[field] && <span className="case-error" id={`${id}-${field}-error`}>{errors[field]}</span>;

  return (
    <div className="case-overlay" onClick={event => { if (event.target === event.currentTarget) onClose(); }}>
      <aside className="case-drawer" role="dialog" aria-modal="true" aria-labelledby={`${id}-title`} aria-describedby={`${id}-notice`} tabIndex={-1} ref={dialog}>
        <header className="case-header">
          <div><p className="case-eyebrow">Invoice details</p><h2 id={`${id}-title`}>{invoice.id}</h2></div>
          <button type="button" className="case-close" onClick={onClose} ref={closeButton} aria-label="Close invoice details">Close <span aria-hidden="true">×</span></button>
        </header>
        <div className="case-content">
          <p className="case-notice" id={`${id}-notice`}>Synthetic demo only. All decisions and history below are local examples. No live KSeF, phone call, posting or tax execution.</p>
          <section className="case-section" aria-labelledby={`${id}-invoice`}>
            <div className="case-section-heading"><h3 id={`${id}-invoice`}>{invoice.supplier}</h3><span className={`case-status case-status-${invoice.status}`}>{STATUS_LABELS[invoice.status]}</span></div>
            <dl className="case-facts">
              <div><dt>Invoice date</dt><dd>{invoice.date}</dd></div>
              <div><dt>Context</dt><dd>{invoice.context}</dd></div>
              <div><dt>Net amount</dt><dd>{money(invoice.netAmount)}</dd></div>
              <div><dt>Invoice VAT</dt><dd>{money(invoice.vatAmount)}</dd></div>
              <div className="case-gross"><dt>Gross amount</dt><dd>{money(invoice.amount)}</dd></div>
            </dl>
            <p className="case-muted">Fixture amounts; invoice VAT does not establish a deductible VAT share.</p>
          </section>
          {invoice.question && <section className="case-section" aria-labelledby={`${id}-question`}>
            <h3 id={`${id}-question`}>Client question</h3><p>{invoice.question}</p>
            {invoice.status === 'waiting_for_client' && <form className="case-form" onSubmit={submit} noValidate>
              <label htmlFor={`${id}-vehicleRegistration`}>Vehicle registration <span className="case-required">(required)</span></label>
              <input {...fieldProps('vehicleRegistration')} value={answer.vehicleRegistration} onChange={event => update('vehicleRegistration', event.target.value)} maxLength={32} autoComplete="off" placeholder="e.g. DEMO 123" />
              {fieldError('vehicleRegistration')}
              <label htmlFor={`${id}-usage`}>Vehicle usage <span className="case-required">(required)</span></label>
              <select {...fieldProps('usage')} value={answer.usage} onChange={event => update('usage', event.target.value)}>
                <option value="">Select usage</option><option value="mixed">Mixed — business and private</option><option value="business">Business only</option>
              </select>
              {fieldError('usage')}
              <label htmlFor={`${id}-purpose`}>Business purpose <span className="case-required">(required)</span></label>
              <textarea {...fieldProps('purpose')} value={answer.purpose} onChange={event => update('purpose', event.target.value)} maxLength={1000} rows={3} placeholder="Describe the purpose of this fuel purchase" />
              {fieldError('purpose')}
              <p className="case-muted">Saving marks this local demo case complete. It does not validate tax treatment or create a verified precedent.</p>
              {failure && <p className="case-error" role="alert">{failure}</p>}
              <button className="case-submit" type="submit" disabled={pending}>{saved ? 'Demo answer recorded' : pending ? 'Saving demo answer…' : 'Save demo answer'}</button>
            </form>}
          </section>}
          {invoice.answer && <section className="case-section" aria-labelledby={`${id}-answer`}>
            <h3 id={`${id}-answer`}>Client answer · synthetic demo</h3>
            <dl className="case-facts"><div><dt>Registration</dt><dd>{invoice.answer.vehicleRegistration}</dd></div><div><dt>Usage</dt><dd>{invoice.answer.usage === 'mixed' ? 'Mixed' : 'Business only'}</dd></div><div className="case-wide"><dt>Purpose</dt><dd>{invoice.answer.purpose}</dd></div></dl>
          </section>}
          <section className="case-section" aria-labelledby={`${id}-reasoning`}>
            <h3 id={`${id}-reasoning`}>Reasoning</h3><p>{invoice.reasoning}</p>
            <p className="case-muted">Precedent: {invoice.precedentId ? `${invoice.precedentId} (synthetic reference)` : 'None. No verified reusable precedent.'}</p>
          </section>
          <section className="case-section" aria-labelledby={`${id}-sources`}>
            <h3 id={`${id}-sources`}>Sources · reference only</h3>
            <ul className="case-sources">{invoice.sources.map(source => <li key={source.url}>
              <a href={source.url} target="_blank" rel="noreferrer">{source.title}<span className="case-sr-only"> (opens in a new tab)</span></a><p className="case-muted">{source.note}</p>
            </li>)}</ul>
          </section>
          <section className="case-section" aria-labelledby={`${id}-timeline`}>
            <h3 id={`${id}-timeline`}>Demo timeline</h3><p className="case-muted">Illustrative sequence, not verified event timestamps.</p>
            <ol className="case-timeline">{invoice.timeline.map((event, index) => <li key={`${index}-${event.title}`}><span className="case-step">{event.time}</span><h4>{event.title}</h4><p>{event.description}</p></li>)}</ol>
          </section>
        </div>
      </aside>
    </div>
  );
}
