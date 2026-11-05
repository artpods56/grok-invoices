'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import '@fontsource/inter/400.css';
import '@fontsource/inter/500.css';
import '@fontsource/inter/600.css';
import {
  ArrowRight, Bell, BookmarkSimple, Buildings, CaretDown,
  ChatCircleText, CheckCircle, Clock, Database, DownloadSimple, Eye, EyeSlash,
  FileText, House, List, MagnifyingGlass, Pulse, Robot, ShieldCheck,
  SlidersHorizontal, Stack, User, WarningCircle, X,
} from '@phosphor-icons/react';
import { STATUS_LABELS, summarizeInvoices, filterInvoices, exportInvoicesCsv } from './domain.js';
import { PlatformDrawer } from './PlatformDrawer.jsx';
import { PlatformSections } from './PlatformSections.jsx';
import { loadPlatformPostings, loadPlatformSnapshot } from './platform.js';

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
const statuses = ['completed', 'waiting_for_client', 'received', 'in_review', 'attention'];
const cardInfo = [
  { status: 'completed', icon: CheckCircle, asset: 'summary-completed.png' },
  { status: 'waiting_for_client', icon: Clock, asset: 'summary-waiting.png' },
  { status: 'attention', icon: WarningCircle, asset: 'summary-blocked.png' },
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
  const [snapshot, setSnapshot] = useState(null);
  const [platformError, setPlatformError] = useState('');
  const [loading, setLoading] = useState(true);
  const [updatedAt, setUpdatedAt] = useState(null);
  const [refreshAttempt, setRefreshAttempt] = useState(0);
  const [now, setNow] = useState(Date.now());
  const invoices = snapshot?.invoices ?? [];
  useEffect(() => {
    let active = true;
    let timer;
    let controller;
    async function refresh() {
      controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 12000);
      setLoading(true);
      try {
        const result = await loadPlatformSnapshot({ signal: controller.signal });
        result.postings = await loadPlatformPostings(result.invoices, { signal: controller.signal });
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
  }, [refreshAttempt]);
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
    .filter(invoice => !contextOnly || ['received', 'in_review'].includes(invoice.status)), [invoices, query, status, contextOnly]);
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
  function navigate(label) { setPage(label); setMobileNav(false); setQuery(''); setStatus('all'); setContextOnly(false); setSelected(new Set()); }
  function toggleSelection(id) { setSelected(previous => { const next = new Set(previous); next.has(id) ? next.delete(id) : next.add(id); return next; }); }
  function toggleAll() { setSelected(previous => { const next = new Set(previous); filtered.forEach(invoice => allSelected ? next.delete(invoice.id) : next.add(invoice.id)); return next; }); }
  function openCase(id) { if (!privateMode) { setActiveId(id); setError(''); } }
  function exportCsv() {
    const rows = selectedVisible.length ? selectedVisible : filtered;
    const blob = new Blob([exportInvoicesCsv(rows)], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a'); link.href = url; link.download = 'grok-invoices.csv';
    document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    setNotice(`Exported ${rows.length} invoice${rows.length === 1 ? '' : 's'}.`);
  }
  const mask = value => privateMode ? '••••••' : value;
  const statusBadge = invoice => <span className={`status-badge ${invoice.status}`}>{STATUS_LABELS[invoice.status]}</span>;

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
        </div>

        <div className="platform-sync" aria-live="polite">
          <div><strong>Platform API · read only</strong><p>Demo company records from the platform API.</p>
            <p>{loading ? 'Refreshing…' : updatedAt ? 'Auto-refresh every 15 seconds.' : 'No snapshot loaded.'} {updatedAt && <>Last updated: {new Date(updatedAt).toLocaleTimeString('en-GB')}. </>}{updatedAt && (platformError || now - updatedAt > 30000) && <strong>Stale snapshot</strong>}</p>
          </div><button className="button" disabled={loading} onClick={() => setRefreshAttempt(value => value + 1)}>{platformError ? 'Retry' : 'Refresh'}</button>
          {platformError && <p className="platform-sync-error" role="alert">{platformError} {snapshot ? 'Showing the last successful snapshot.' : 'No platform data is displayed.'}</p>}
        </div>
        {(page === 'Invoices' || page === 'Overview') && <div className="summary-grid">{cardInfo.map(({ status: cardStatus, icon: Icon, asset }) => <button key={cardStatus} className={`summary-card ${status === cardStatus ? 'summary-selected' : ''}`} style={{ backgroundImage: `url(/assets/${asset})` }} onClick={() => { setStatus(status === cardStatus ? 'all' : cardStatus); setContextOnly(false); setPage('Invoices'); }} aria-pressed={status === cardStatus}>
          <span className="summary-icon"><Icon size={20} weight="regular" /></span><strong>{mask(!snapshot ? '—' : summary[cardStatus])}</strong><span className="summary-title">{STATUS_LABELS[cardStatus]}</span><span className="summary-caption">Platform records</span>
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
          {!filtered.length && <div className="empty-state"><MagnifyingGlass size={26} /><h3>{!snapshot ? loading ? 'Loading platform records' : 'Platform unavailable' : !invoices.length ? 'No invoices yet' : 'No matching invoices'}</h3><p>{!snapshot ? 'The dashboard will show records after a successful API read.' : !invoices.length ? 'No invoices are recorded yet.' : 'Try another search or clear your filters.'}</p><button className="button" onClick={() => { setQuery(''); setStatus('all'); setContextOnly(false); }}>Clear filters</button></div>}
        </section> : <section className="support-panel">
          <div className="support-heading"><h2>{page === 'Questions' ? 'Client questions' : page}</h2><span className="muted">Platform records · read only</span></div>
          {privateMode ? <p className="panel-empty">Private details hidden.</p> : <PlatformSections page={page} invoices={filtered} snapshot={snapshot} onInspect={openCase} />}
        </section>}
        {privateMode && <div className="privacy-note"><EyeSlash size={15} />Private details hidden. Show details to inspect cases or export.</div>}
        <div className="toast" role="status" aria-live="polite">{notice}</div>
        {error && <div className="error-notice" role="alert">{error}<button className="icon-button" aria-label="Dismiss error" onClick={() => setError('')}><X size={15} /></button></div>}
      </main>
    </div>

    <PlatformDrawer invoice={privateMode ? null : activeInvoice} onClose={() => setActiveId(null)} />
    {modal && <Modal title={modal === 'filters' ? 'Invoice filters' : modal === 'notifications' ? 'Notifications' : 'Demo workspace'} onClose={() => setModal(null)}>
      {modal === 'filters' && <><p>Choose which cases appear in the invoice table.</p><label className="field-label">Status<select value={status} onChange={event => setStatus(event.target.value)}><option value="all">All statuses</option>{statuses.map(value => <option key={value} value={value}>{STATUS_LABELS[value]}</option>)}</select></label><label className="filter-checkbox"><input type="checkbox" checked={contextOnly} onChange={event => setContextOnly(event.target.checked)} />Needs attention only<span>Received or in review</span></label><div className="dialog-actions"><button className="button" onClick={() => { setStatus('all'); setContextOnly(false); }}>Reset filters</button><button className="button button-dark" onClick={() => setModal(null)}>Show results</button></div></>}
      {modal === 'notifications' && <><p>Current counts:</p><button className="notification-row" onClick={() => { navigate('Questions'); setModal(null); }}><Clock size={20} /><span>{mask(summary.waiting_for_client)} waiting for client</span><ArrowRight size={16} /></button><button className="notification-row" onClick={() => { navigate('Invoices'); setStatus('attention'); setModal(null); }}><WarningCircle size={20} /><span>{mask(summary.attention)} needing attention</span><ArrowRight size={16} /></button></>}
      {modal === 'profile' && <><div className="dialog-emblem"><ShieldCheck size={30} /></div><h3>Demo company · Grok Invoices</h3><p>A read-only view of the platform's records.</p><button className="button" onClick={() => { navigate('Company context'); setModal(null); }}>View company context<ArrowRight size={16} /></button></>}
    </Modal>}
  </div>;
}
