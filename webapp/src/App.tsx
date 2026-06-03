/* eslint-disable @typescript-eslint/no-explicit-any */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Icon } from './components/Icon';
import { initTelegram, syncTheme, setupBackButton, setupMainButton, getTg } from './lib/telegram';
import { ListScreen } from './screens/ListScreen';
import { DomainScreen } from './screens/DomainScreen';
import type { WebAppDomain } from './lib/api';

const TABS = [
  { id: 'list', icon: 'language', label: 'Домены' },
  { id: 'dashboard', icon: 'monitoring', label: 'Дашборд' },
  { id: 'calendar', icon: 'calendar_month', label: 'Календарь' },
  { id: 'alerts', icon: 'notifications', label: 'Алерты' },
  { id: 'more', icon: 'menu', label: 'Ещё' },
] as const;

type TabId = typeof TABS[number]['id'];

export default function App() {
  const [, setTheme] = useState<'light' | 'dark'>('light');
  const [tab, setTab] = useState<TabId>('list');
  const [stack, setStack] = useState<any[]>([]);
  const [toastMsg, setToastMsg] = useState<{ msg: string; icon?: string } | null>(null);
  const bodyRef = useRef<HTMLDivElement>(null);

  initTelegram();

  useEffect(() => { syncTheme(setTheme); }, []);

  const top = stack[stack.length - 1] || null;
  const showBack = !!top;

  const back = useCallback(() => setStack(p => p.slice(0, -1)), []);

  useEffect(() => { setupBackButton(back, showBack); }, [showBack, back]);

  const toast = useCallback((msg: string, icon = 'check_circle') => {
    setToastMsg({ msg, icon });
    const w = window as any; clearTimeout(w.__t); w.__t = setTimeout(() => setToastMsg(null), 2200);
  }, []);

  const push = (s: any) => { setStack(p => [...p, s]); if (bodyRef.current) bodyRef.current.scrollTop = 0; };
  const goTab = (t: TabId) => { setStack([]); setTab(t); };
  const openDomain = (d: WebAppDomain) => push({ type: 'domain', id: d.id });

  useEffect(() => {
    if (top) setupMainButton({ text: 'Обновить', onClick: () => toast('Обновить (stub)'), visible: true });
    else getTg()?.MainButton?.hide();
  }, [top, toast]);

  const showTabbar = !top;
  let headerTitle: string = TABS.find(t => t.id === tab)!.label;
  if (top) headerTitle = 'Домен';

  const demoD = { id: 1, name: 'demo.ru', unicode: 'demo.ru', noData: false, isWishlist: false, daysLeft: 12, health: 81, subCount: 3, groups: [], notify: { expiry: true, ns: false, registrar: true, status: true }, flags: [], cost: 0, registrar: 'Demo' } as WebAppDomain;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100dvh' }}>
      <div className="tg-header">
        {showBack ? <button className="tg-hbtn" onClick={back}><Icon name="arrow_back" /></button> : <button className="tg-hbtn" onClick={() => toast('Меню')}><Icon name="menu" /></button>}
        <div className="tg-htitle"><b>{headerTitle}</b></div>
      </div>

      <div ref={bodyRef} style={{ flex: 1, overflow: 'auto' }}>
        {!top && tab === 'list' && <ListScreen onOpenDomain={openDomain} toast={toast} bodyRef={bodyRef} />}
        {top && <DomainScreen d={demoD} onBack={back} toast={toast} onRefresh={() => toast('refresh')} />}
        {!top && tab !== 'list' && <div className="tg-pad tg-card"><h3>{headerTitle} (stub 0069)</h3></div>}
      </div>

      {showTabbar && (
        <div className="tg-tabbar">
          {TABS.map(t => <button key={t.id} className={`tg-tab ${tab === t.id ? 'active' : ''}`} onClick={() => goTab(t.id)}><Icon name={t.icon} /><span>{t.label}</span></button>)}
        </div>
      )}
      {toastMsg && <div className="tg-toast"><Icon name={toastMsg.icon || 'info'} />{toastMsg.msg}</div>}
    </div>
  );
}
