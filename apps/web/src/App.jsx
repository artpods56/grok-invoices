'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import '@fontsource/inter/400.css';
import '@fontsource/inter/500.css';
import '@fontsource/inter/600.css';
import {
  ArrowRight, ArrowSquareOut, Bell, BookmarkSimple, Buildings, CaretDown,
  ChatCircleText, CheckCircle, Clock, Database, DownloadSimple, Eye, EyeSlash,
  FileText, House, List, MagnifyingGlass, Plus, Pulse, Robot, ShieldCheck,
  SlidersHorizontal, Stack, User, WarningCircle, X,
} from '@phosphor-icons/react';
import {
  createDemoInvoices, STATUS_LABELS, summarizeInvoices, filterInvoices,
  exportInvoicesCsv, resolveDemoQuestion,
} from './domain.js';
import { CaseDrawer } from './CaseDrawer.jsx';
import { PlatformDrawer } from './PlatformDrawer.jsx';
import { PlatformSections } from './PlatformSections.jsx';
import { loadPlatformSnapshot } from './platform.js';

const navigation = [
  { label: 'Overview', icon: House },
  { label: 'Invoices', icon: FileText },
  { label: 'Questions', icon: ChatCircleText },
  { label: 'Decisions', icon: Stack },
  { label: 'Company context', icon: Buildings },
  { label: 'Agents', icon: Robot, workspace: true },
  { label: 'Sources', icon: Database },
  { label: 'Precedents', icon: BookmarkSimple },
  { label: 'Activity', icon: Pulse },
];
const demoStatuses = ['completed', 'waiting_for_client', 'blocked'];
const cardInfo = [
  { status: 'completed', icon: CheckCircle, asset: 'summary-completed.png' },
  { status: 'waiting_for_client', icon: Clock, asset: 'summary-waiting.png' },
  { status: 'blocked', icon: WarningCircle, asset: 'summary-blocked.png' },
];
const money = value => `PLN ${Number(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const dateLabel = date => new Date(`${date}T12:00:00`).toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric' });

function Modal({ title, children, onClose }) {
  const ref = useRef(null);
  useEffect(() => {
    const previous = document.activeElement;
    ref.current?.querySelector('button, input, a')?.focus();
    const oldOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = oldOverflow; previous?.focus(); };
  }, []);
  function trapFocus(event) {
    if (event.key !== 'Tab') return;
    const elements = [...ref.current.querySelectorAll('button:not(:disabled), a[href], input, select, textarea, [tabindex="0"]')];
    const first = elements[0];
    const last = elements.at(-1);
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
    if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
  }
  return <div className="modal-backdrop" onClick={event => { if (event.target === event.currentTarget) onClose(); }}>
    <section ref={ref} className="dialog" role="dialog" aria-modal="true" aria-labelledby="dialog-title" onKeyDown={trapFocus}>
      <div className="dialog-heading"><h2 id="dialog-title">{title}</h2><button className="icon-button" onClick={onClose} aria-label="Close dialog"><X size={19} /></button></div>
      {children}
    </section>
  </div>;
}

export function App() {
  const [demoInvoices, setDemoInvoices] = useState(createDemoInvoices);
  const [dataset, setDataset] = useState('platform');
  const [snapshot, setSnapshot] = useState(null);
  const [platformError, setPlatformError] = useState('');
  const [loading, setLoading] = useState(true);
  const [updatedAt, setUpdatedAt] = useState(null);
  const [refreshAttempt, setRefreshAttempt] = useState(0);
  const [now, setNow] = useState(Date.now());
  const platform = dataset === 'platform';
  const invoices = platform ? snapshot?.invoices ?? [] : demoInvoices;
  const statuses = platform ? ['completed', 'waiting_for_client', 'received', 'in_review', 'attention'] : demoStatuses;
  const cards = cardInfo.map(card => platform && card.status === 'blocked' ? { ...card, status: 'attention' } : card);
  useEffect(() => {
    if (!platform) return;
    let active = true;
    let timer;
    let controller;
    async function refresh() {
      controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 12000);
      setLoading(true);
      try {
        const result = await loadPlatformSnapshot({ signal: controller.signal });
        if (active) { setSnapshot(result); setUpdatedAt(Date.now()); setPlatformError(''); }
      } catch (failure) {
        if (active) setPlatformError(failure?.name === 'AbortError' ? 'Platform request timed out. Please retry.' : failure instanceof Error ? failure.message : 'Could not load the platform.');
      } finally {
        clearTimeout(timeout); controller.abort();
        if (active) { setLoading(false); timer = setTimeout(refresh, 15000); }
      }
    }
    refresh();
    return () => { active = false; clearTimeout(timer); controller?.abort(); };
  }, [platform, refreshAttempt]);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const [page, setPage] = useState('Invoices');
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('all');
  const [selected, setSelected] = useState(new Set());
  const [activeId, setActiveId] = useState(null);
  const [privateMode, setPrivateMode] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);
  const [modal, setModal] = useState(null);
  const [statusMenu, setStatusMenu] = useState(false);
  const [contextOnly, setContextOnly] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const searchRef = useRef(null);
  const checkAllRef = useRef(null);
  const summary = useMemo(() => summarizeInvoices(invoices), [invoices]);
  const filtered = useMemo(() => filterInvoices(invoices, { query, status: status === 'all' ? undefined : status })
    .filter(invoice => !contextOnly || (platform ? ['received', 'in_review'].includes(invoice.status) : ['waiting_for_client', 'blocked'].includes(invoice.status))), [invoices, query, status, contextOnly, platform]);
  const activeInvoice = invoices.find(invoice => invoice.id === activeId) ?? null;
  const selectedVisible = filtered.filter(invoice => selected.has(invoice.id));
  const allSelected = filtered.length > 0 && selectedVisible.length === filtered.length;
  useEffect(() => { if (checkAllRef.current) checkAllRef.current.indeterminate = selectedVisible.length > 0 && !allSelected; }, [selectedVisible.length, allSelected]);
  useEffect(() => {
    function keydown(event) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); searchRef.current?.focus(); }
      if (event.key === 'Escape') { setModal(null); setActiveId(null); setStatusMenu(false); setMobileNav(false); }
    }
    document.addEventListener('keydown', keydown);
    return () => document.removeEventListener('keydown', keydown);
  }, []);
  useEffect(() => { if (!notice) return; const timer = setTimeout(() => setNotice(''), 5000); return () => clearTimeout(timer); }, [notice]);
  function changeDataset(value) {
    setDataset(value); setSelected(new Set()); setQuery(''); setStatus('all');
    setContextOnly(false); setActiveId(null); setModal(null); setError('');
    setPlatformError(''); setNotice(''); setStatusMenu(false);
    if (value === 'platform') { setSnapshot(null); setUpdatedAt(null); setLoading(true); }
  }
  function navigate(label) { setPage(label); setMobileNav(false); setQuery(''); setStatus('all'); setContextOnly(false); setSelected(new Set()); }
  function toggleSelection(id) { setSelected(previous => { const next = new Set(previous); next.has(id) ? next.delete(id) : next.add(id); return next; }); }
  function toggleAll() { setSelected(previous => { const next = new Set(previous); filtered.forEach(invoice => allSelected ? next.delete(invoice.id) : next.add(invoice.id)); return next; }); }
  function openCase(id) { if (!privateMode) { setActiveId(id); setError(''); } }
  function resolve(id, answer) {
    try {
      if (platform) throw new Error('Platform records are read only.');
      const next = resolveDemoQuestion(demoInvoices, id, answer);
      setDemoInvoices(next); setError(''); setNotice('Synthetic answer saved. Demo case updated locally.');
    } catch (caught) { setError(caught.message || 'Please complete all demo answer fields.'); throw caught; }
  }
  function exportCsv() {
    const rows = selectedVisible.length ? selectedVisible : filtered;
    const blob = new Blob([exportInvoicesCsv(rows)], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a'); link.href = url; link.download = `grok-invoices-${dataset}.csv`;
    document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    setNotice(`Exported ${rows.length} ${platform ? 'platform' : 'synthetic'} invoice${rows.length === 1 ? '' : 's'}.`);
  }
  const mask = value => privateMode ? '••••••' : value;
  const statusBadge = invoice => <span className={`status-badge ${invoice.status}`}>{STATUS_LABELS[invoice.status]}</span>;
  const caseButton = invoice => <button className="text-button" disabled={privateMode} onClick={() => openCase(invoice.id)}>{mask(invoice.id)}<ArrowRight size={15} /></button>;

  return <div className="app-shell">
    {mobileNav && <button className="nav-backdrop" aria-label="Close navigation" onClick={() => setMobileNav(false)} />}
    <aside className={`sidebar ${mobileNav ? 'is-open' : ''}`} aria-label="Main navigation">
      <button className="company-switcher" onClick={() => { navigate('Company context'); }}>
        <img src="/assets/icon.svg" width="30" height="30" alt="Grok Invoices" />
        <span><span className="company-caption">Demo company</span><strong>Grok Invoices</strong></span><CaretDown size={13} />
      </button>
      <nav>{navigation.map(({ label, icon: Icon, workspace }) => <div key={label}>
        {workspace && <div className="workspace-label">Workspace</div>}
        <button className={`nav-item ${page === label ? 'active' : ''}`} onClick={() => navigate(label)} aria-current={page === label ? 'page' : undefined}>
          <Icon size={19} weight="regular" /><span>{label}</span>{(label === 'Invoices' || label === 'Company context') && <CaretDown className="nav-caret" size={13} />}
        </button>
      </div>)}</nav>
      <div className="assistant-card"><p>Your accounting<br />assistant</p><button className="button button-dark" onClick={() => setModal('bot')}>Open Grok Bot</button></div>
    </aside>

    <div className="workspace">
      <header className="topbar">
        <button className="icon-button mobile-menu" onClick={() => setMobileNav(true)} aria-label="Open navigation"><List size={22} /></button>
        <div className="breadcrumb"><span>Dashboard</span><span className="breadcrumb-separator">›</span><strong>{page}</strong></div>
        <div className="topbar-actions">
          <label className="search"><MagnifyingGlass size={18} /><input ref={searchRef} aria-label="Search invoices" placeholder="Search..." disabled={privateMode} value={query} onChange={event => setQuery(event.target.value)} /><kbd>⌘ K</kbd></label>
          <button className={`icon-button ${privateMode ? 'is-toggled' : ''}`} aria-label={privateMode ? 'Show private details' : 'Hide private details'} title={privateMode ? 'Show private details' : 'Hide private details'} aria-pressed={privateMode} onClick={() => { setPrivateMode(!privateMode); setActiveId(null); setModal(null); setNotice(''); setError(''); setQuery(''); setSelected(new Set()); }}>{privateMode ? <Eye size={18} /> : <EyeSlash size={18} />}</button>
          <button className="icon-button" onClick={() => setModal('notifications')} aria-label="View notifications"><Bell size={18} /></button>
          <button className="avatar-button" onClick={() => setModal('profile')} aria-label="Demo company profile"><User size={20} /></button>
        </div>
      </header>

      <main id="main-content">
        <div className="page-heading"><div><h1>{page}</h1><p>{page === 'Invoices' || page === 'Overview' ? 'Track every invoice, question, and accounting decision.' : 'Inspect the context behind your invoice cases.'}</p></div>
          <div className="heading-actions"><label className="dataset-selector"><span>Dataset</span><select aria-label="Dataset" value={dataset} onChange={event => changeDataset(event.target.value)}><option value="platform">Platform API</option><option value="synthetic">Synthetic demo</option></select></label><button className="button button-dark" onClick={() => setModal('bot')}><Plus size={15} />Open Grok Bot</button></div>
        </div>

        {platform && <div className="platform-sync" aria-live="polite">
          <div><strong>Platform API · read only</strong><p>Same-origin /api · Demo records, not a live KSeF connection.</p>
            <p>{loading ? 'Refreshing…' : updatedAt ? 'Auto-refresh every 15 seconds.' : 'No snapshot loaded.'} {updatedAt && <>Last updated: {new Date(updatedAt).toLocaleTimeString('en-GB')}. </>}{updatedAt && (platformError || now - updatedAt > 30000) && <strong>Stale snapshot</strong>}</p>
          </div><button className="button" disabled={loading} onClick={() => setRefreshAttempt(value => value + 1)}>{platformError ? 'Retry' : 'Refresh'}</button>
          {platformError && <p className="platform-sync-error" role="alert">{platformError} {snapshot ? 'Showing the last successful snapshot.' : 'No platform data is displayed. Select Synthetic demo to explore local fixtures.'}</p>}
        </div>}
        {(page === 'Invoices' || page === 'Overview') && <div className="summary-grid">{cards.map(({ status: cardStatus, icon: Icon, asset }) => <button key={cardStatus} className={`summary-card ${status === cardStatus ? 'summary-selected' : ''}`} style={{ backgroundImage: `url(/assets/${asset})` }} onClick={() => { setStatus(status === cardStatus ? 'all' : cardStatus); setContextOnly(false); setPage('Invoices'); }} aria-pressed={status === cardStatus}>
          <span className="summary-icon"><Icon size={20} weight="regular" /></span><strong>{mask(platform && !snapshot ? '—' : summary[cardStatus])}</strong><span className="summary-title">{STATUS_LABELS[cardStatus]}</span><span className="summary-caption">{platform ? 'Platform records' : 'Synthetic demo'}</span>
        </button>)}</div>}

        {(page === 'Invoices' || page === 'Overview') ? <section className="invoice-panel" aria-label="Invoices">
          <div className="table-toolbar"><h2>{!privateMode && selectedVisible.length ? `${selectedVisible.length} selected` : 'All invoices'}</h2><div className="table-controls">
            <button className={`button ${status === 'all' && !contextOnly ? 'button-dark' : ''}`} onClick={() => { setStatus('all'); setContextOnly(false); }}>All</button>
            <div className="dropdown"><button className={`button ${status !== 'all' ? 'filter-active' : ''}`} aria-expanded={statusMenu} aria-controls="status-options" onClick={() => setStatusMenu(!statusMenu)}>{status === 'all' ? 'Status' : STATUS_LABELS[status]}<CaretDown size={13} /></button>
              {statusMenu && <><button className="dropdown-dismiss" aria-label="Close status filter" onClick={() => setStatusMenu(false)} /><div id="status-options" className="dropdown-menu">{['all', ...statuses].map(value => <button key={value} aria-pressed={status === value} onClick={() => { setStatus(value); setStatusMenu(false); }}>{value === 'all' ? 'All statuses' : STATUS_LABELS[value]}{status === value && <CheckCircle size={16} />}</button>)}</div></>}
            </div>
            <button className={`button ${contextOnly ? 'filter-active' : ''}`} onClick={() => setModal('filters')}><SlidersHorizontal size={15} />{contextOnly ? 'Filters · 1' : 'Add filters'}</button>
            <button className="button" disabled={privateMode || !filtered.length} title={privateMode ? 'Show private details to export' : 'Export visible or selected invoices'} onClick={exportCsv}><DownloadSimple size={15} />Export</button>
          </div></div>
          <div className="table-scroll"><table><thead><tr><th className="checkbox-cell"><input ref={checkAllRef} type="checkbox" aria-label="Select all visible invoices" checked={allSelected} disabled={privateMode || !filtered.length} onChange={toggleAll} /></th><th>Date</th><th>Supplier</th><th>Status</th><th>Amount</th><th>Invoice No.</th><th>Context</th></tr></thead>
            <tbody>{filtered.map(invoice => <tr key={invoice.id} className={selected.has(invoice.id) ? 'row-selected' : ''}>
              <td className="checkbox-cell"><input type="checkbox" disabled={privateMode} checked={selected.has(invoice.id)} aria-label={`Select ${privateMode ? 'invoice' : invoice.id}`} onChange={() => toggleSelection(invoice.id)} /></td>
              <td>{mask(dateLabel(invoice.date))}</td><td><button className="supplier-button" disabled={privateMode} onClick={() => openCase(invoice.id)}><span className="supplier-avatar">{privateMode ? <User size={15} /> : invoice.initials}</span><span>{mask(invoice.supplier)}</span></button></td>
              <td>{privateMode ? mask('') : statusBadge(invoice)}</td><td className="amount">{mask(money(invoice.amount))}</td><td><button className="invoice-link" disabled={privateMode} onClick={() => openCase(invoice.id)}>{mask(invoice.id)}</button></td><td><button className="context-button" disabled={privateMode} onClick={() => openCase(invoice.id)}>{mask(invoice.context)}</button></td>
            </tr>)}</tbody></table></div>
          {!filtered.length && <div className="empty-state"><MagnifyingGlass size={26} /><h3>{platform && !snapshot ? loading ? 'Loading platform records' : 'Platform unavailable' : !invoices.length ? 'No invoices yet' : 'No matching invoices'}</h3><p>{platform && !snapshot ? 'The dashboard will show records after a successful API read.' : !invoices.length ? 'No invoices are recorded in this dataset.' : 'Try another search or clear your filters.'}</p><button className="button" onClick={() => { setQuery(''); setStatus('all'); setContextOnly(false); }}>Clear filters</button></div>}
        </section> : <section className="support-panel">
          <div className="support-heading"><h2>{page === 'Questions' ? 'Client questions' : page}</h2><span className="muted">{platform ? 'Platform records · read only' : 'Synthetic demo only'}</span></div>
          {privateMode ? <p className="panel-empty">Private details hidden.</p> : platform ? <PlatformSections page={page} invoices={filtered} snapshot={snapshot} onInspect={openCase} /> : <>
          {page === 'Questions' && <>{filtered.filter(invoice => invoice.question).map(invoice => <article className="detail-row" key={invoice.id}><ChatCircleText size={21} /><div><h3>{mask(invoice.question)}</h3><p>{mask(invoice.supplier)} · {invoice.answer ? 'Demo answer recorded' : 'Awaiting context'}</p></div>{statusBadge(invoice)}{caseButton(invoice)}</article>)}{!filtered.some(invoice => invoice.question) && <p className="panel-empty">No questions match your search.</p>}</>}
          {page === 'Decisions' && <>{filtered.map(invoice => <article className="detail-row" key={invoice.id}><Stack size={21} /><div><h3>{mask(invoice.context)}</h3><p>{mask(invoice.reasoning)}</p></div>{statusBadge(invoice)}{caseButton(invoice)}</article>)}{!filtered.length && <p className="panel-empty">No decisions match your search.</p>}</>}
          {page === 'Company context' && <div className="context-content"><Buildings size={30} /><h3>Demo company</h3><p>This workspace contains {invoices.length} synthetic purchase invoices. No taxpayer account, KSeF credentials, or phone connection is configured.</p><div className="context-facts"><span>Dataset<strong>Synthetic fixtures</strong></span><span>Currency<strong>PLN</strong></span><span>Linked precedent cases<strong>{invoices.filter(invoice => invoice.precedentId).length} linked case(s)</strong></span></div><button className="button" onClick={() => navigate('Invoices')}>Inspect invoices<ArrowRight size={15} /></button></div>}
          {page === 'Agents' && <div className="agent-list">{[{ name: 'Invoice agent', description: 'Inspect synthetic invoices and linked case context.' }, { name: 'Regulatory agent', description: 'Inspect fixture reasoning, sources, and missing facts.' }, { name: 'Client agent', description: 'Explore a synthetic client question walkthrough.' }].map(agent => <article className="detail-row" key={agent.name}><Robot size={25} /><div><h3>{agent.name}</h3><p>{agent.description}</p></div><span className="neutral-badge">Synthetic role</span></article>)}<p className="panel-note">Synthetic role descriptions only. This view does not report platform agent activity.</p><button className="button" onClick={() => setModal('bot')}>Open demo walkthrough<ArrowRight size={15} /></button></div>}
          {page === 'Sources' && <>{filtered.flatMap(invoice => invoice.sources.map((source, index) => <article className="detail-row" key={`${invoice.id}-${index}`}><Database size={21} /><div><h3>{mask(source.title)}</h3><p>{mask(source.note)}</p></div>{!privateMode && /^https?:\/\//i.test(source.url) && <a className="text-button" href={source.url} target="_blank" rel="noreferrer">View source<ArrowSquareOut size={15} /></a>}{caseButton(invoice)}</article>))}<p className="panel-note">Source links are supplied by synthetic fixtures. No live legal research was performed here.</p></>}
          {page === 'Precedents' && <>{filtered.filter(invoice => invoice.precedentId).map(invoice => <article className="detail-row" key={invoice.id}><BookmarkSimple size={21} /><div><h3>{mask(invoice.precedentId)}</h3><p>{mask(invoice.context)} · {mask(invoice.supplier)}</p></div>{caseButton(invoice)}</article>)}{!filtered.some(invoice => invoice.precedentId) && <p className="panel-empty">No linked precedents in the current results.</p>}<p className="panel-note">A linked demo precedent is fixture context, not a validated accounting rule.</p></>}
          {page === 'Activity' && <>{filtered.flatMap(invoice => invoice.timeline.map((event, index) => <article className="detail-row" key={`${invoice.id}-${index}`}><Pulse size={20} /><div><h3>{mask(event.title)}</h3><p>{mask(event.description)}</p></div><span className="muted">{event.time}</span>{caseButton(invoice)}</article>))}{!filtered.length && <p className="panel-empty">No activity matches your search.</p>}</>}
          </>}
        </section>}
        {privateMode && <div className="privacy-note"><EyeSlash size={15} />Private details hidden. Show details to inspect cases or export.</div>}
        <div className="toast" role="status" aria-live="polite">{notice}</div>
        {error && <div className="error-notice" role="alert">{error}<button className="icon-button" aria-label="Dismiss error" onClick={() => setError('')}><X size={15} /></button></div>}
      </main>
    </div>

    {platform ? <PlatformDrawer invoice={privateMode ? null : activeInvoice} onClose={() => setActiveId(null)} /> : <CaseDrawer invoice={privateMode ? null : activeInvoice} onClose={() => setActiveId(null)} onResolve={resolve} />}
    {modal && <Modal title={modal === 'bot' ? 'Meet your Grok Bot' : modal === 'filters' ? 'Invoice filters' : modal === 'notifications' ? 'Notifications' : 'Demo workspace'} onClose={() => setModal(null)}>
      {modal === 'bot' && <><div className="dialog-emblem"><Robot size={30} /></div><span className="neutral-badge">Connection not configured</span><p>No chat or phone connection is configured in this dashboard. Use invoice details to inspect recorded platform activity.</p><div className="walkthrough-card"><span className="eyebrow">SYNTHETIC CASE WALKTHROUGH</span><h3>A fuel invoice needs context</h3><p>Inspect the PLN 246.00 unknown-vehicle example, supply demo vehicle details, and see the local case update.</p><button className="button button-dark" disabled={privateMode} onClick={() => { changeDataset('synthetic'); navigate('Invoices'); setActiveId('DEMO-003'); }}>{platform ? 'Switch to synthetic walkthrough' : 'Start synthetic walkthrough'}<ArrowRight size={16} /></button>{privateMode && <p>Show private details to start the walkthrough.</p>}</div><p className="dialog-footnote">Demo changes stay in this browser session. No call is placed, invoice booked, or external service contacted.</p></>}
      {modal === 'filters' && <><p>Choose which cases appear in the invoice table.</p><label className="field-label">Status<select value={status} onChange={event => setStatus(event.target.value)}><option value="all">All statuses</option>{statuses.map(value => <option key={value} value={value}>{STATUS_LABELS[value]}</option>)}</select></label><label className="filter-checkbox"><input type="checkbox" checked={contextOnly} onChange={event => setContextOnly(event.target.checked)} />Needs attention only<span>{platform ? 'Received or in review' : 'Waiting for client or blocked'}</span></label><div className="dialog-actions"><button className="button" onClick={() => { setStatus('all'); setContextOnly(false); }}>Reset filters</button><button className="button button-dark" onClick={() => setModal(null)}>Show results</button></div></>}
      {modal === 'notifications' && <><p>No live notification service is configured. Current dataset counts:</p><button className="notification-row" onClick={() => { navigate('Questions'); setModal(null); }}><Clock size={20} /><span>{mask(summary.waiting_for_client)} waiting for client</span><ArrowRight size={16} /></button><button className="notification-row" onClick={() => { navigate('Invoices'); setStatus(platform ? 'attention' : 'blocked'); setModal(null); }}><WarningCircle size={20} /><span>{mask(platform ? summary.attention : summary.blocked)} {platform ? 'needing attention' : 'blocked case(s)'}</span><ArrowRight size={16} /></button></>}
      {modal === 'profile' && <><div className="dialog-emblem"><ShieldCheck size={30} /></div><h3>Demo company · Grok Invoices</h3><p>A read-only platform inspection workspace with a separate synthetic walkthrough. No chat is configured here.</p><button className="button" onClick={() => { navigate('Company context'); setModal(null); }}>View company context<ArrowRight size={16} /></button></>}
    </Modal>}
  </div>;
}
