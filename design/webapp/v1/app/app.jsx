/* ============================================================
   Root App — навигация, header, tabbar, MainButton, sheets
   ============================================================ */

// ── Shared overlays (global) ────────────────────────────────
function Sheet({ title, onClose, children }) {
  return (
    <div className="tg-sheet-mask" onClick={onClose}>
      <div className="tg-sheet" onClick={e => e.stopPropagation()}>
        <div className="tg-sheet-grab" />
        {title && <div className="tg-sheet-head"><h3>{title}</h3><button className="tg-hbtn" style={{ width: 32, height: 32 }} onClick={onClose}><Icon name="close" /></button></div>}
        {children}
      </div>
    </div>
  );
}
window.Sheet = Sheet;

const TABS = [
  { id: 'list', icon: 'language', label: 'Домены' },
  { id: 'dashboard', icon: 'monitoring', label: 'Дашборд' },
  { id: 'calendar', icon: 'calendar_month', label: 'Календарь' },
  { id: 'alerts', icon: 'notifications', label: 'Алерты' },
  { id: 'more', icon: 'menu', label: 'Ещё' },
];

function App() {
  const [theme, setTheme] = useState('light');
  const [domains, setDomains] = useState(window.DATA.domains);
  const [alerts, setAlerts] = useState(window.DATA.alerts);
  const [tab, setTab] = useState('list');
  const [stack, setStack] = useState([]); // pushed screens
  const [sheet, setSheet] = useState(null);
  const [toastMsg, setToastMsg] = useState(null);
  const bodyRef = useRef(null);

  const [st, setSt] = useState({ query: '', filter: 'all', sort: 'expiry', groupBy: 'none', selMode: false, sel: new Set(), groupView: null });
  const [addVal, setAddVal] = useState('');
  const [addGroup, setAddGroup] = useState(null);

  useEffect(() => { document.documentElement.setAttribute('data-theme', theme); }, [theme]);

  const toast = useCallback((msg, icon = 'check_circle') => {
    setToastMsg({ msg, icon });
    clearTimeout(window.__t); window.__t = setTimeout(() => setToastMsg(null), 2200);
  }, []);

  const top = stack[stack.length - 1] || null;
  const push = (s) => { setStack(p => [...p, s]); if (bodyRef.current) bodyRef.current.scrollTop = 0; };
  const back = () => setStack(p => p.slice(0, -1));
  const openDomain = (d) => push({ type: 'domain', id: d.id });
  const openDomainId = (id) => { const d = domains.find(x => x.id === id); if (d) openDomain(d); };

  const go = (opts) => {
    setStack([]);
    if (opts.tab) setTab(opts.tab);
    if (opts.screen) { setTab('more'); push({ type: opts.screen }); return; }
    setSt(s => ({ ...s,
      filter: opts.filter ?? (opts.groupFilter ? 'all' : s.filter),
      sort: opts.sort ?? s.sort,
      groupView: opts.groupFilter ?? null,
      selMode: false, sel: new Set(),
    }));
  };

  const setDomain = (nd) => setDomains(ds => ds.map(d => d.id === nd.id ? nd : d));
  const removeDomain = (id) => { setDomains(ds => ds.filter(d => d.id !== id)); };

  const curDomain = top && top.type === 'domain' ? domains.find(d => d.id === top.id) : null;

  // ── header ────────────────────────────────────────────────
  let headerTitle = TABS.find(t => t.id === tab).label, headerSub = null, headerCenter = false, headerMenu = null;
  if (top) {
    headerCenter = true;
    const titles = { domain: curDomain ? curDomain.name : '', add: 'Добавить домен', groups: 'Группы и теги', wishlist: 'Wishlist', settings: 'Настройки', stats: 'Статистика', import: 'Импорт доменов' };
    headerTitle = titles[top.type] || '';
    if (top.type === 'domain' && curDomain) {
      const s = statusOf(curDomain);
      headerSub = <span style={{ color: s.dot }}>{daysText(curDomain)}</span>;
      headerMenu = 'domain';
    }
  } else if (tab === 'list' && st.selMode) {
    headerTitle = st.sel.size ? `Выбрано: ${st.sel.size}` : 'Выберите домены';
    headerCenter = false;
  }

  // ── MainButton config ─────────────────────────────────────
  let mainBtn = null;
  if (top) {
    if (top.type === 'add') mainBtn = { label: 'Добавить на слежение', icon: 'add', disabled: !/^[a-zа-я0-9-]+\.[a-zа-я0-9.-]+$/i.test(addVal.trim()), onClick: () => { toast(addVal.trim() + ' добавлен на слежение'); setAddVal(''); back(); } };
    else if (top.type === 'import') mainBtn = { label: 'Импортировать 214 доменов', icon: 'download_done', green: true, onClick: () => { toast('214 доменов добавлено'); back(); } };
    else if (top.type === 'settings') mainBtn = { label: 'Сохранить', icon: 'check', onClick: () => { toast('Настройки сохранены'); back(); } };
  } else if (tab === 'list' && st.selMode && st.sel.size > 0) {
    mainBtn = { label: 'Действия', count: st.sel.size, icon: 'bolt', onClick: () => setSheet({ type: 'bulk' }) };
  }

  const showTabbar = !top;
  const showFab = !top && tab === 'list' && !st.selMode;

  // bulk actions
  const bulkAct = (kind) => {
    const ids = st.sel;
    if (kind === 'notify_on' || kind === 'notify_off') {
      setDomains(ds => ds.map(d => ids.has(d.id) ? { ...d, notify: { ...d.notify, expiry: kind === 'notify_on' } } : d));
      toast(`Уведомления ${kind === 'notify_on' ? 'включены' : 'выключены'} для ${ids.size}`);
    } else if (kind === 'remove') { setDomains(ds => ds.filter(d => !ids.has(d.id))); toast(`Удалено: ${ids.size}`); }
    else if (kind === 'export') toast('CSV с выбранными доменами готов', 'download');
    else if (kind === 'group') toast('Выбор группы', 'folder');
    setSt(s => ({ ...s, sel: new Set(), selMode: false }));
    setSheet(null);
  };

  return (
    <div className="tg-phone">
      <div className="tg-screen">
        {/* status bar */}
        <div className="tg-statusbar">
          <span>9:41</span>
          <div className="tg-sb-right">
            <Icon name="signal_cellular_alt" /><Icon name="wifi" /><Icon name="battery_full" style={{ transform: 'rotate(90deg)' }} />
          </div>
        </div>

        {/* header */}
        <div className={"tg-header" + (headerCenter ? " center" : "")}>
          {top
            ? <button className="tg-hbtn" onClick={back}><Icon name="arrow_back_ios_new" style={{ fontSize: 20 }} /></button>
            : st.selMode
              ? <button className="tg-hbtn" onClick={() => setSt(s => ({ ...s, selMode: false, sel: new Set() }))}><Icon name="close" /></button>
              : <button className="tg-hbtn" onClick={() => setSheet({ type: 'menu' })}><Icon name="menu" /></button>}
          <div className="tg-htitle">
            <b>{headerTitle}</b>
            {headerSub && <span>{headerSub}</span>}
            {!top && !st.selMode && tab === 'list' && <span style={{ color: 'var(--pv-fg-muted)' }}>{domains.length} на слежении</span>}
          </div>
          {headerMenu === 'domain'
            ? <button className="tg-hbtn" onClick={() => setSheet({ type: 'domainMenu' })}><Icon name="more_vert" /></button>
            : !top && tab === 'list' && !st.selMode
              ? <button className="tg-hbtn" onClick={() => { setSt(s => ({ ...s, selMode: true, sel: new Set() })); }}><Icon name="checklist" /></button>
              : <div style={{ width: 38 }} />}
        </div>

        {/* body */}
        <div className="tg-body" ref={bodyRef}>
          {top && top.type === 'domain' && curDomain && <DomainScreen d={curDomain} setDomain={setDomain} toast={toast} onAction={(a) => { if (a === 'refresh') toast('Запущена проверка домена', 'refresh'); else if (a === 'raw') setSheet({ type: 'raw' }); else toast('Ссылка скопирована', 'link'); }} />}
          {top && top.type === 'add' && <AddScreen value={addVal} setValue={setAddVal} group={addGroup} setGroup={setAddGroup} />}
          {top && top.type === 'groups' && <GroupsScreen domains={domains} go={go} toast={toast} />}
          {top && top.type === 'wishlist' && <WishlistScreen domains={domains} onOpen={openDomain} go={go} />}
          {top && top.type === 'settings' && <SettingsScreen user={window.DATA.user} toast={toast} />}
          {top && top.type === 'stats' && <StatsScreen domains={domains} />}
          {top && top.type === 'import' && <ImportScreen toast={toast} />}

          {!top && tab === 'list' && <ListScreen domains={domains} st={st} setSt={setSt} onOpen={openDomain} bodyRef={bodyRef} toast={toast} />}
          {!top && tab === 'dashboard' && <DashboardScreen domains={domains} onOpen={openDomain} go={go} />}
          {!top && tab === 'calendar' && <CalendarScreen domains={domains} onOpen={openDomain} toast={toast} />}
          {!top && tab === 'alerts' && <AlertsScreen alerts={alerts} domains={domains} onOpenId={openDomainId} markAll={() => { setAlerts(as => as.map(a => ({ ...a, unread: false }))); toast('Все отмечены прочитанными'); }} />}
          {!top && tab === 'more' && <MoreScreen domains={domains} user={window.DATA.user} go={go} toast={toast} theme={theme} setTheme={setTheme} />}

          {showFab && <button className="tg-fab" onClick={() => push({ type: 'add' })}><Icon name="add" /></button>}
          {toastMsg && <div className="tg-toast"><Icon name={toastMsg.icon} />{toastMsg.msg}</div>}
        </div>

        {/* MainButton */}
        {mainBtn && (
          <div className="tg-mainbtn-wrap">
            <button className={"tg-mainbtn" + (mainBtn.green ? " green" : "") + (mainBtn.accent ? " accent" : "")} disabled={mainBtn.disabled} onClick={mainBtn.onClick}>
              {mainBtn.icon && <Icon name={mainBtn.icon} />}{mainBtn.label}
              {mainBtn.count != null && <span className="tg-mb-count">{mainBtn.count}</span>}
            </button>
          </div>
        )}

        {/* tabbar */}
        {showTabbar && (
          <div className="tg-tabbar">
            {TABS.map(t => {
              const badge = t.id === 'alerts' ? alerts.filter(a => a.unread).length : 0;
              return (
                <button key={t.id} className={"tg-tab" + (tab === t.id ? " active" : "")} onClick={() => { setTab(t.id); if (bodyRef.current) bodyRef.current.scrollTop = 0; }}>
                  <Icon name={t.icon} />{t.label}
                  {badge > 0 && <span className="tg-tab-badge">{badge}</span>}
                </button>
              );
            })}
          </div>
        )}

        {/* sheets */}
        {sheet && sheet.type === 'menu' && (
          <Sheet title="Whois Watcher" onClose={() => setSheet(null)}>
            <div className="tg-menu">
              <div className="tg-menu-row" onClick={() => { setSheet(null); push({ type: 'add' }); }}><Icon name="add_circle" />Добавить домен</div>
              <div className="tg-menu-row" onClick={() => { setSheet(null); go({ screen: 'import' }); }}><Icon name="upload_file" />Импорт из файла</div>
              <div className="tg-menu-row" onClick={() => { setSheet(null); toast('CSV готов', 'download'); }}><Icon name="download" />Экспорт в CSV</div>
              <div className="tg-menu-row" onClick={() => { setSheet(null); go({ screen: 'settings' }); }}><Icon name="settings" />Настройки</div>
              <div className="tg-menu-row" onClick={() => { setSheet(null); setTheme(theme === 'dark' ? 'light' : 'dark'); }}><Icon name="contrast" />Сменить тему<span className="tg-menu-val">{theme === 'dark' ? 'тёмная' : 'светлая'}</span></div>
            </div>
          </Sheet>
        )}
        {sheet && sheet.type === 'bulk' && (
          <Sheet title={`Действия · ${st.sel.size}`} onClose={() => setSheet(null)}>
            <div className="tg-menu">
              <div className="tg-menu-row" onClick={() => bulkAct('notify_on')}><Icon name="notifications_active" />Включить уведомления</div>
              <div className="tg-menu-row" onClick={() => bulkAct('notify_off')}><Icon name="notifications_off" />Выключить уведомления</div>
              <div className="tg-menu-row" onClick={() => bulkAct('group')}><Icon name="folder" />Добавить в группу</div>
              <div className="tg-menu-row" onClick={() => bulkAct('export')}><Icon name="download" />Экспорт выбранных</div>
              <div className="tg-menu-row danger" onClick={() => bulkAct('remove')}><Icon name="delete" />Снять со слежения</div>
            </div>
          </Sheet>
        )}
        {sheet && sheet.type === 'domainMenu' && curDomain && (
          <Sheet title={curDomain.name} onClose={() => setSheet(null)}>
            <div className="tg-menu">
              <div className="tg-menu-row" onClick={() => { setSheet(null); toast('Запущена проверка домена', 'refresh'); }}><Icon name="refresh" />Обновить данные</div>
              <div className="tg-menu-row" onClick={() => { setSheet(null); setSheet({ type: 'raw' }); }}><Icon name="data_object" />Полный WHOIS-ответ</div>
              <div className="tg-menu-row" onClick={() => { setSheet(null); toast('Ссылка скопирована', 'link'); }}><Icon name="ios_share" />Поделиться</div>
              <div className="tg-menu-row danger" onClick={() => { setSheet(null); removeDomain(curDomain.id); back(); toast('Снят со слежения'); }}><Icon name="visibility_off" />Снять со слежения</div>
            </div>
          </Sheet>
        )}
        {sheet && sheet.type === 'raw' && curDomain && (
          <Sheet title="Полный WHOIS-ответ" onClose={() => setSheet(null)}>
            <div style={{ padding: '0 16px 20px' }}>
              <pre style={{ background: 'var(--pv-muted)', borderRadius: 10, padding: 14, fontSize: 11, lineHeight: 1.5, overflowX: 'auto', color: 'var(--pv-fg-body)', fontFamily: 'var(--pv-font-mono)' }}>
{`Domain Name: ${curDomain.name.toUpperCase()}
Registry Domain ID: ${curDomain.id.toUpperCase()}-RU
Registrar: ${curDomain.registrar}
Registrar URL: https://${curDomain.registrarHost}
Creation Date: ${curDomain.registered}
Registry Expiry Date: ${curDomain.expires || '—'}
Updated Date: ${curDomain.updated}
Domain Status: ${curDomain.flags.join('\n               ')}
Name Server: ${(curDomain.dns ? curDomain.dns.ns : []).join('\n             ')}
DNSSEC: ${curDomain.dns && curDomain.dns.dnssec ? 'signedDelegation' : 'unsigned'}
>>> Last update: ${curDomain.lastCheck} <<<`}
              </pre>
            </div>
          </Sheet>
        )}
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
