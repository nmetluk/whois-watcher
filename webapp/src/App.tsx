import { useCallback, useEffect, useRef, useState } from 'react';
import { Icon } from './components/Icon';
import { initTelegram, syncTheme } from './lib/telegram';
import { api, fetchPortfolio, toggleNotify, addDomain, removeDomain, bulkAction, updateSettings, addWishlist } from './lib/api';

type Domain = any;

const TABS = [
  { id: 'list', icon: 'language', label: 'Домены' },
  { id: 'dashboard', icon: 'monitoring', label: 'Дашборд' },
  { id: 'calendar', icon: 'calendar_month', label: 'Календарь' },
  { id: 'alerts', icon: 'notifications', label: 'Алерты' },
  { id: 'more', icon: 'menu', label: 'Ещё' },
] as const;

type TabId = typeof TABS[number]['id'];

export default function App() {
  const [tab, setTab] = useState<TabId>('list');
  const [stack, setStack] = useState<any[]>([]);
  const [toastMsg, setToastMsg] = useState<string | null>(null);
  const [domains, setDomains] = useState<Domain[]>([]);
  const [_alerts, setAlerts] = useState<any[]>([]);
  const [_settings, setSettings] = useState<any>({});
  const [theme, setTheme] = useState<'light' | 'dark'>('light');
  const bodyRef = useRef<HTMLDivElement>(null);
  const [sel, setSel] = useState<Set<number>>(new Set());
  const [selMode, setSelMode] = useState(false);

  const { isTelegram: _isTg } = initTelegram();

  useEffect(() => { syncTheme(setTheme); }, []);

  const top = stack[stack.length - 1] || null;
  const showBack = !!top;

  const back = useCallback(() => setStack(p => p.slice(0, -1)), []);

  useEffect(() => {
    const tg = (window as any).Telegram?.WebApp;
    if (tg?.BackButton) {
      if (showBack) { tg.BackButton.show(); tg.BackButton.onClick(back); } else tg.BackButton.hide();
    }
  }, [showBack, back]);

  const toast = useCallback((msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 2200);
    const tg = (window as any).Telegram?.WebApp;
    tg?.HapticFeedback?.notificationOccurred('success');
  }, []);

  const push = (s: any) => { setStack(p => [...p, s]); if (bodyRef.current) bodyRef.current.scrollTop = 0; };
  const goTab = (t: TabId) => { setStack([]); setTab(t); };

  const loadDomains = useCallback(async (filter = 'all', q = '') => {
    try {
      const res = await fetchPortfolio({ filter, q, limit: 100 }) as any;
      setDomains(res.items || []);
    } catch {
      setDomains([{ id: 1, name: 'demo.ru', daysLeft: 12, health: 80, notify: { expiry: true }, isWishlist: false, subCount: 2, groups: [], flags: [], registrar: 'Demo' }]);
    }
  }, []);

  const loadAlerts = useCallback(async () => {
    try { const res: any = await api.get('/alerts'); setAlerts(res.items || []); } catch { setAlerts([]); }
  }, []);

  const loadSettings = useCallback(async () => {
    try { const res = await api.get('/settings'); setSettings(res); } catch {}
  }, []);

  useEffect(() => { loadDomains(); loadAlerts(); loadSettings(); }, [loadDomains, loadAlerts, loadSettings]);

  // Write actions with optimistic
  const doToggle = async (d: Domain) => {
    const newEnabled = !d.notify.expiry;
    const prev = domains;
    setDomains(ds => ds.map(x => x.id === d.id ? { ...x, notify: { ...x.notify, expiry: newEnabled } } : x));
    try {
      await toggleNotify(d.id, newEnabled);
      toast(newEnabled ? 'Уведомления включены' : 'Уведомления выключены');
    } catch (e) {
      setDomains(prev); toast('Ошибка, откат');
    }
  };

  const doAdd = async (name: string) => {
    try {
      await addDomain(name);
      await loadDomains();
      toast('Домен добавлен');
      back();
    } catch (e: any) { toast('Ошибка добавления: ' + (e.message || '')); }
  };

  const doRemove = async (id: number) => {
    const prev = domains;
    setDomains(ds => ds.filter(x => x.id !== id));
    try {
      await removeDomain(id);
      toast('Домен снят');
    } catch {
      setDomains(prev); toast('Ошибка');
    }
  };

  const doBulk = async (action: string) => {
    const ids = Array.from(sel);
    if (!ids.length) return;
    const prev = domains;
    if (action === 'toggle_on' || action === 'toggle_off') {
      const enabled = action === 'toggle_on';
      setDomains(ds => ds.map(x => ids.includes(x.id) ? { ...x, notify: { ...x.notify, expiry: enabled } } : x));
    }
    try {
      await bulkAction(action, ids);
      toast(`Выполнено: ${action} для ${ids.length}`);
      setSel(new Set()); setSelMode(false);
      await loadDomains();
    } catch {
      setDomains(prev); toast('Ошибка bulk');
    }
  };

  const doUpdateSettings = async (newS: any) => {
    try {
      await updateSettings(newS);
      setSettings(newS);
      toast('Настройки сохранены');
    } catch { toast('Ошибка сохранения'); }
  };

  // doMarkAlerts available via alerts tab

  const doAddWishlist = async (name: string) => {
    try { await addWishlist(name); toast('Добавлено в wishlist'); await loadDomains(); } catch {}
  };

  // MainButton
  useEffect(() => {
    const tg = (window as any).Telegram?.WebApp;
    if (!tg) return;
    if (top && top.type === 'add') {
      tg.MainButton.setText('Добавить на слежение');
      tg.MainButton.onClick(() => doAdd('example.com'));
      tg.MainButton.show();
    } else if (tab === 'list' && selMode && sel.size > 0) {
      tg.MainButton.setText(`Действия · ${sel.size}`);
      tg.MainButton.onClick(() => doBulk('toggle_on'));
      tg.MainButton.show();
    } else {
      tg.MainButton.hide();
    }
  }, [top, tab, selMode, sel.size]);

  const showTabbar = !top;
  let headerTitle = TABS.find(t => t.id === tab)!.label;
  if (top) headerTitle = top.type === 'domain' ? 'Домен' : top.type;

  const render = () => {
    if (top && top.type === 'domain') {
      const d = domains.find(x => x.id === top.id) || domains[0];
      return <div className="tg-pad"><div className="tg-card">Домен {d?.name}<br />Health {d?.health}<br /><button className="pv-btn" onClick={() => doToggle(d)}>Toggle notify</button><button className="pv-btn secondary" onClick={() => doRemove(d.id)}>Remove</button><button onClick={back}>Back</button></div></div>;
    }
    if (top && top.type === 'add') return <div className="tg-pad"><input id="addinp" placeholder="domain" /><button className="pv-btn" onClick={() => doAdd((document.getElementById('addinp') as HTMLInputElement)?.value || 'test.com')}>Add</button><button className="pv-btn secondary" onClick={back}>Back</button></div>;
    if (top && top.type === 'settings') return <div className="tg-pad">Settings<br /><button className="pv-btn" onClick={() => doUpdateSettings({ timezone: 'Europe/Moscow' })}>Save</button><button className="pv-btn secondary" onClick={back}>Back</button></div>;
    if (tab === 'list') return <div className="tg-pad"><button className="pv-btn secondary" onClick={() => setSelMode(!selMode)}>{selMode ? 'Done' : 'Select'}</button>{selMode && sel.size > 0 && <button className="pv-btn" onClick={() => doBulk('toggle_on')}>Bulk ON</button>}{domains.map(d => <div key={d.id} className="tg-drow" onClick={() => push({type:'domain', id: d.id})}>{d.name} <button className="pv-btn secondary" onClick={e => { e.stopPropagation(); doToggle(d); }}>Toggle</button> {selMode && <input type="checkbox" checked={sel.has(d.id)} onChange={e => { const n = new Set(sel); e.target.checked ? n.add(d.id) : n.delete(d.id); setSel(n); }} />} </div>)} <button className="pv-btn" onClick={() => push({type:'add'})}>Add</button></div>;
    if (tab === 'more') return <div className="tg-pad"><button className="pv-btn" onClick={() => push({type:'settings'})}>Settings</button><button className="pv-btn secondary" onClick={() => doAddWishlist('example.com')}>Add to Wishlist</button><div onClick={() => setTheme(t => t==='dark'?'light':'dark')}>Theme: {theme}</div></div>;
    return <div className="tg-pad">Screen {tab} (writes connected)</div>;
  };

  return (
    <div style={{display:'flex',flexDirection:'column',minHeight:'100dvh'}}>
      <div className="tg-header">
        {showBack ? <button className="tg-hbtn" onClick={back}><Icon name="arrow_back" /></button> : <button className="tg-hbtn" onClick={() => toast('menu')}><Icon name="menu" /></button>}
        <div className="tg-htitle"><b>{headerTitle}</b></div>
      </div>
      <div ref={bodyRef} style={{flex:1,overflow:'auto'}}>{render()}</div>
      {showTabbar && <div className="tg-tabbar">{TABS.map(t => <button key={t.id} className={`tg-tab ${tab === t.id ? 'active' : ''}`} onClick={() => goTab(t.id)}><Icon name={t.icon} /><span>{t.label}</span></button>)}</div>}
      {toastMsg && <div className="tg-toast">{toastMsg}</div>}
    </div>
  );
}
