/* ============================================================
   Список доменов — поиск, фильтры, сортировка, группировка,
   мультивыбор, быстрый джамп.
   ============================================================ */
const FILTERS = [
  { id: 'all',     label: 'Все',          test: () => true },
  { id: 'soon',    label: 'Истекающие',   icon: 'hourglass_bottom', test: d => d.daysLeft != null && d.daysLeft >= 0 && d.daysLeft < 30 },
  { id: 'crit',    label: 'Критичные',    icon: 'priority_high', test: d => d.daysLeft != null && d.daysLeft >= 0 && d.daysLeft < 7 },
  { id: 'problem', label: 'С проблемами', icon: 'gpp_maybe', test: d => d.flags.some(f => ['clientHold','pendingDelete','redemptionPeriod'].includes(f)) || (d.ssl && d.ssl.daysLeft < 0) },
  { id: 'expired', label: 'Истёкшие',     icon: 'event_busy', test: d => d.daysLeft != null && d.daysLeft < 0 },
  { id: 'nodata',  label: 'Без данных',   test: d => d.noData || d.daysLeft == null },
  { id: 'silent',  label: 'Без уведомлений', icon: 'notifications_off', test: d => !d.notify.expiry && !d.isWishlist },
  { id: 'wish',    label: 'Wishlist',     icon: 'target', test: d => d.isWishlist },
];
const SORTS = [
  { id: 'expiry', label: 'По сроку' },
  { id: 'name',   label: 'По алфавиту' },
  { id: 'added',  label: 'По добавлению' },
  { id: 'health', label: 'По health-score' },
];

function ListScreen(props) {
  const { domains, st, setSt, onOpen, bodyRef, toast } = props;
  const { query, filter, sort, groupBy, selMode, sel } = st;

  const filterDef = FILTERS.find(f => f.id === filter) || FILTERS[0];

  const filtered = useMemo(() => {
    let arr = domains.filter(d => filterDef.test(d));
    if (st.groupView) arr = arr.filter(d => d.groups.includes(st.groupView));
    if (query.trim()) {
      const q = query.trim().toLowerCase();
      arr = arr.filter(d => d.name.toLowerCase().includes(q) || d.registrar.toLowerCase().includes(q));
    }
    arr = [...arr];
    if (sort === 'name') arr.sort((a,b) => a.name.localeCompare(b.name, 'ru'));
    else if (sort === 'added') arr.sort((a,b) => b.id.localeCompare(a.id));
    else if (sort === 'health') arr.sort((a,b) => a.health - b.health);
    else arr.sort((a,b) => (a.daysLeft ?? 1e9) - (b.daysLeft ?? 1e9));
    return arr;
  }, [domains, filter, query, sort]);

  // grouping into sections
  const sections = useMemo(() => {
    if (groupBy === 'none') return [{ key: '_', label: null, items: filtered }];
    const map = new Map();
    const order = [];
    filtered.forEach(d => {
      let keys;
      if (groupBy === 'status') { const s = statusOf(d); keys = [[s.key, s.label]]; }
      else { keys = d.groups.length ? d.groups.map(g => [g, groupById(g) ? groupById(g).name : g]) : [['_none','Без группы']]; }
      keys.forEach(([k, lbl]) => {
        if (!map.has(k)) { map.set(k, { key: k, label: lbl, items: [] }); order.push(k); }
        map.get(k).items.push(d);
      });
    });
    if (groupBy === 'status') {
      const rank = { red: 0, gold: 1, gray: 2, green: 3, wish: 4 };
      order.sort((a,b) => (rank[a] ?? 9) - (rank[b] ?? 9));
    }
    return order.map(k => map.get(k));
  }, [filtered, groupBy]);

  const activeGroup = st.groupView ? groupById(st.groupView) : null;

  // jump index (letters when name-sorted, months when expiry-sorted)
  const sectionRefs = useRef({});
  const jumpIndex = useMemo(() => {
    if (groupBy !== 'none') return null;
    if (sort === 'name') {
      const seen = {}; const items = [];
      filtered.forEach(d => { const L = d.name[0].toUpperCase(); if (!seen[L]) { seen[L] = true; items.push({ k: L, label: L }); } });
      return items.length > 6 ? items : null;
    }
    return null;
  }, [filtered, sort, groupBy]);

  const jumpTo = (k) => {
    const el = sectionRefs.current[k];
    if (el && bodyRef.current) bodyRef.current.scrollTop = el.offsetTop - 92;
  };

  const toggleSel = (id) => {
    const next = new Set(sel);
    next.has(id) ? next.delete(id) : next.add(id);
    setSt(s => ({ ...s, sel: next }));
  };

  const [showSort, setShowSort] = useState(false);

  // letter rail for name sort (no grouping)
  let cursor = null;

  return (
    <>
      {/* search */}
      <div className="tg-search-sticky">
        <div className="tg-search">
          <Icon name="search" />
          <input value={query} placeholder="Поиск домена или регистратора"
            onChange={e => setSt(s => ({ ...s, query: e.target.value }))} />
          {query && <Icon name="close" style={{ fontSize: 18, color: 'var(--pv-fg-muted)' }} onClick={() => setSt(s => ({ ...s, query: '' }))} />}
        </div>
        <div className="tg-chips">
          {FILTERS.map(f => {
            const n = domains.filter(f.test).length;
            if (f.id !== 'all' && n === 0) return null;
            return (
              <button key={f.id} className={"tg-chip2" + (filter === f.id ? " accent active" : "")}
                onClick={() => setSt(s => ({ ...s, filter: f.id }))}>
                {f.icon && <Icon name={f.icon} />}{f.label}<span className="tg-chip-n">{n}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* control strip: sort + group + select */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', borderBottom: '1px solid var(--pv-border)', background: 'var(--pv-panel)' }}>
        {activeGroup && (
          <button className="tg-chip2 accent active" style={{ height: 28 }} onClick={() => setSt(s => ({ ...s, groupView: null }))}>
            <Icon name={activeGroup.icon} />{activeGroup.name}<Icon name="close" style={{ fontSize: 14 }} />
          </button>
        )}
        <button className="tg-chip2" onClick={() => setShowSort(true)} style={{ height: 28 }}>
          <Icon name="swap_vert" />{SORTS.find(s => s.id === sort).label}
        </button>
        <button className={"tg-chip2" + (groupBy !== 'none' ? " active" : "")} style={{ height: 28 }}
          onClick={() => setSt(s => ({ ...s, groupBy: s.groupBy === 'none' ? 'group' : s.groupBy === 'group' ? 'status' : 'none' }))}>
          <Icon name="segment" />{groupBy === 'none' ? 'Без групп' : groupBy === 'group' ? 'По клиентам' : 'По статусу'}
        </button>
        <div style={{ flex: 1 }} />
        <button className={"tg-chip2" + (selMode ? " active" : "")} style={{ height: 28 }}
          onClick={() => setSt(s => ({ ...s, selMode: !s.selMode, sel: new Set() }))}>
          <Icon name={selMode ? 'close' : 'checklist'} />{selMode ? 'Отмена' : 'Выбрать'}
        </button>
      </div>

      <div style={{ position: 'relative' }}>
        {sections.map(sec => (
          <div key={sec.key} ref={el => { if (el) sectionRefs.current[sec.key] = el; }}>
            {sec.label && (
              <div className="tg-list-head">
                {groupBy === 'status' && <span className="pv-dot" style={{ width: 8, height: 8, borderRadius: '50%', background: ({red:'var(--pv-red)',gold:'var(--pv-gold)',green:'var(--pv-green)',gray:'var(--pv-fg-subtle)',wish:'var(--pv-violet)'}[sec.key]) }} />}
                {sec.label}<span className="tg-lh-count">{sec.items.length}</span>
              </div>
            )}
            {sec.items.map(d => {
              // name-sort letter divider
              let divider = null;
              if (jumpIndex && groupBy === 'none') {
                const L = d.name[0].toUpperCase();
                if (L !== cursor) { cursor = L; divider = <div key={'L'+L} ref={el => { if (el) sectionRefs.current[L] = el; }} className="tg-list-head">{L}</div>; }
              }
              return (
                <React.Fragment key={d.id}>
                  {divider}
                  <DomainRow d={d} selMode={selMode} selected={sel.has(d.id)}
                    onClick={() => selMode ? toggleSel(d.id) : onOpen(d)} />
                </React.Fragment>
              );
            })}
          </div>
        ))}
        {filtered.length === 0 && (
          <div className="tg-empty2">
            <Icon name="search_off" /><b>Ничего не найдено</b>
            <div>Измените фильтр или запрос</div>
          </div>
        )}
        <div style={{ padding: '14px', textAlign: 'center', color: 'var(--pv-fg-subtle)', fontSize: 12 }}>
          {filtered.length} {plural(filtered.length, 'домен', 'домена', 'доменов')} · обновлено сегодня в 09:00
        </div>
      </div>

      {/* alphabet rail */}
      {jumpIndex && (
        <div style={{ position: 'absolute', right: 2, top: 120, bottom: 70, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 0, zIndex: 7 }}>
          {jumpIndex.map(j => (
            <button key={j.k} onClick={() => jumpTo(j.k)}
              style={{ border: 'none', background: 'transparent', color: 'var(--pv-cta)', fontSize: 10, fontWeight: 700, padding: '1px 5px', cursor: 'pointer', lineHeight: 1.3 }}>
              {j.label}
            </button>
          ))}
        </div>
      )}

      {/* sort sheet */}
      {showSort && (
        <Sheet title="Сортировка" onClose={() => setShowSort(false)}>
          <div className="tg-menu">
            {SORTS.map(s => (
              <div key={s.id} className="tg-menu-row" onClick={() => { setSt(x => ({ ...x, sort: s.id })); setShowSort(false); }}>
                <Icon name={{ expiry:'schedule', name:'sort_by_alpha', added:'history', health:'monitor_heart' }[s.id]} />
                {s.label}
                {sort === s.id && <Icon name="check" className="tg-menu-chev" style={{ color: 'var(--pv-cta)' }} />}
              </div>
            ))}
          </div>
        </Sheet>
      )}
    </>
  );
}

function DomainRow({ d, selMode, selected, onClick }) {
  const s = statusOf(d);
  return (
    <div className={"tg-drow" + (selected ? " sel" : "")} onClick={onClick}>
      {selMode && <div className="tg-drow-check"><Icon name="check" /></div>}
      <div className={"tg-puck " + s.color}>{puckText(d)}</div>
      <div className="tg-drow-main">
        <div className="tg-drow-name">
          {d.name}
          {!d.notify.expiry && !d.isWishlist && <Icon name="notifications_off" />}
        </div>
        <div className="tg-drow-sub">
          {d.isWishlist ? <span>жду освобождения</span> : <>
            <span>{d.expires || 'нет данных'}</span>
            <span>·</span>
            <span>{d.registrar}</span>
          </>}
        </div>
      </div>
      <div className="tg-drow-right">
        <div style={{ fontSize: 12, fontWeight: 700, color: s.dot }}>{daysText(d)}</div>
        <div className="tg-mini-tags">
          {d.groups.slice(0, 1).map(g => <GroupTag key={g} id={g} sm />)}
          {d.ssl && d.ssl.daysLeft < 0 && <span className="tg-mini-tag" style={{ background: 'rgba(230,64,58,0.12)', color: 'var(--pv-red)' }}>SSL</span>}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { ListScreen, FILTERS, SORTS });
