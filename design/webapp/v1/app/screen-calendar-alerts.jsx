/* ============================================================
   Календарь истечений (+ iCal) и лента алертов
   ============================================================ */
const MONTHS = ['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'];
const DOW = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс'];

function parseDate(s) { const [d, m, y] = s.split('.').map(Number); return new Date(y, m - 1, d); }

function CalendarScreen({ domains, onOpen, toast }) {
  const today = window.DATA.TODAY;
  const [view, setView] = useState({ y: today.getFullYear(), m: today.getMonth() });

  const events = useMemo(() => {
    const map = {};
    domains.forEach(d => {
      if (!d.expires || d.isWishlist) return;
      const dt = parseDate(d.expires);
      const key = `${dt.getFullYear()}-${dt.getMonth()}-${dt.getDate()}`;
      (map[key] = map[key] || []).push(d);
    });
    return map;
  }, [domains]);

  const first = new Date(view.y, view.m, 1);
  let startDow = (first.getDay() + 6) % 7; // Mon=0
  const daysInMonth = new Date(view.y, view.m + 1, 0).getDate();
  const cells = [];
  for (let i = 0; i < startDow; i++) cells.push(null);
  for (let dd = 1; dd <= daysInMonth; dd++) cells.push(dd);

  const [selDay, setSelDay] = useState(null);
  const move = (delta) => { let m = view.m + delta, y = view.y; if (m < 0) { m = 11; y--; } if (m > 11) { m = 0; y++; } setView({ y, m }); setSelDay(null); };

  const monthList = useMemo(() => {
    const arr = domains.filter(d => !d.isWishlist && d.expires && parseDate(d.expires).getMonth() === view.m && parseDate(d.expires).getFullYear() === view.y);
    return arr.sort((a,b) => parseDate(a.expires) - parseDate(b.expires));
  }, [domains, view]);

  const selList = selDay ? (events[`${view.y}-${view.m}-${selDay}`] || []) : null;

  return (
    <div className="tg-pad tg-pad-b">
      <div className="tg-cal">
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 12 }}>
          <button className="tg-hbtn" style={{ width: 32, height: 32 }} onClick={() => move(-1)}><Icon name="chevron_left" /></button>
          <div style={{ flex: 1, textAlign: 'center', fontSize: 16, fontWeight: 700, color: 'var(--pv-fg)' }}>{MONTHS[view.m]} {view.y}</div>
          <button className="tg-hbtn" style={{ width: 32, height: 32 }} onClick={() => move(1)}><Icon name="chevron_right" /></button>
        </div>
        <div className="tg-cal-grid">
          {DOW.map(d => <div key={d} className="tg-cal-dow">{d}</div>)}
          {cells.map((dd, i) => {
            if (!dd) return <div key={i} />;
            const ev = events[`${view.y}-${view.m}-${dd}`];
            const isToday = view.y === today.getFullYear() && view.m === today.getMonth() && dd === today.getDate();
            const n = ev ? ev.length : 0;
            const heat = n === 0 ? '' : n <= 1 ? 'heat-1' : n <= 3 ? 'heat-2' : 'heat-3';
            const hasCrit = ev && ev.some(d => d.daysLeft != null && d.daysLeft < 7);
            return (
              <div key={i} className={"tg-cal-cell " + heat + (isToday ? ' today' : '') + (n ? ' has' : '') + (selDay === dd ? '' : '')}
                onClick={() => n && setSelDay(selDay === dd ? null : dd)}
                style={selDay === dd ? { outline: '2px solid var(--pv-cta)' } : null}>
                {dd}
                {n > 0 && <div className="tg-cal-dots"><i style={{ background: hasCrit ? 'var(--pv-red)' : 'var(--pv-gold)' }} />{n > 1 && <i style={{ background: 'var(--pv-fg-subtle)' }} />}</div>}
              </div>
            );
          })}
        </div>
      </div>

      <button className="pv-btn" style={{ width: '100%', justifyContent: 'center', marginTop: 12 }} onClick={() => toast('Файл expirations.ics готов к экспорту', 'event_available')}>
        <Icon name="calendar_add_on" />Экспортировать в календарь (iCal)
      </button>

      {selList && (
        <>
          <div className="tg-section-label">{selDay} {MONTHS[view.m].toLowerCase()} · {selList.length} {plural(selList.length, 'домен','домена','доменов')}</div>
          <div className="tg-card">
            {selList.map(d => <AgendaRow key={d.id} d={d} onOpen={onOpen} />)}
          </div>
        </>
      )}

      <div className="tg-section-label">Истекают в {MONTHS[view.m].toLowerCase()}</div>
      {monthList.length === 0
        ? <div className="tg-empty2" style={{ padding: '36px' }}><Icon name="event_available" /><b>В этом месяце пусто</b></div>
        : <div className="tg-card">{monthList.map(d => <AgendaRow key={d.id} d={d} onOpen={onOpen} showDay />)}</div>}
    </div>
  );
}

function AgendaRow({ d, onOpen, showDay }) {
  const s = statusOf(d);
  const dt = parseDate(d.expires);
  return (
    <div className="tg-irow tap" onClick={() => onOpen(d)}>
      {showDay && <div className="tg-puck" style={{ width: 36, height: 36, flexDirection: 'column', gap: 0 }}>
        <span style={{ fontSize: 15 }}>{dt.getDate()}</span>
      </div>}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--pv-fg)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.name}</div>
        <div style={{ fontSize: 12, color: s.dot }}>{daysText(d)} · {d.cost.toLocaleString('ru-RU')} ₽</div>
      </div>
      <span style={{ width: 8, height: 8, borderRadius: '50%', background: s.dot, flexShrink: 0 }} />
    </div>
  );
}

// ── Alerts feed ─────────────────────────────────────────────
function AlertsScreen({ alerts, domains, onOpenId, markAll }) {
  const [filter, setFilter] = useState('all');
  const types = [
    { id: 'all', label: 'Все' },
    { id: 'unread', label: 'Непрочитанные' },
    { id: 'expiry', label: 'Сроки' },
    { id: 'ssl', label: 'SSL' },
    { id: 'changes', label: 'Изменения' },
  ];
  const filtered = alerts.filter(a => {
    if (filter === 'all') return true;
    if (filter === 'unread') return a.unread;
    if (filter === 'expiry') return ['expiry','expiry_soon','expired'].includes(a.type);
    if (filter === 'ssl') return a.type === 'ssl';
    if (filter === 'changes') return ['ns','registrar','status','subdomain','dmarc','freed'].includes(a.type);
    return true;
  });
  const unread = alerts.filter(a => a.unread).length;
  return (
    <>
      <div className="tg-search-sticky" style={{ paddingBottom: 6 }}>
        <div className="tg-chips" style={{ paddingTop: 0, marginTop: 0 }}>
          {types.map(t => (
            <button key={t.id} className={"tg-chip2" + (filter === t.id ? " active" : "")} onClick={() => setFilter(t.id)}>
              {t.label}{t.id === 'unread' && unread > 0 && <span className="tg-chip-n">{unread}</span>}
            </button>
          ))}
        </div>
      </div>
      {unread > 0 && (
        <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '8px 14px' }}>
          <button className="pv-btn pv-btn-sm pv-btn-ghost" onClick={markAll}><Icon name="done_all" />Прочитать все</button>
        </div>
      )}
      {filtered.length === 0
        ? <div className="tg-empty2"><Icon name="notifications_off" /><b>Уведомлений нет</b><div>Здесь появятся изменения по вашим доменам</div></div>
        : filtered.map(a => (
          <div key={a.id} className={"tg-alert" + (a.unread ? " unread" : "")} onClick={() => onOpenId(a.domainId)}>
            <div className={"tg-alert-ico " + a.sev}><Icon name={a.icon} /></div>
            <div className="tg-alert-main">
              <div className="tg-alert-dom">{a.domain}</div>
              <div className="tg-alert-txt">{a.text}</div>
              <div className="tg-alert-when">{a.when}</div>
            </div>
            <Icon name="chevron_right" style={{ color: 'var(--pv-fg-subtle)', alignSelf: 'center' }} />
          </div>
        ))}
      <div className="tg-pad-b" />
    </>
  );
}

Object.assign(window, { CalendarScreen, AlertsScreen });
