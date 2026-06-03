/* ============================================================
   Дашборд портфеля — health, KPI, распределение, бюджет, риски
   ============================================================ */
function DashboardScreen({ domains, onOpen, go }) {
  const agg = useMemo(() => {
    const a = { total: domains.length, expired: 0, crit: 0, soon: 0, ok: 0, nodata: 0, wish: 0, silent: 0,
      ssl90: 0, sslExp: 0, noDmarc: 0, cost: 0, health: 0, subs: 0 };
    domains.forEach(d => {
      if (d.isWishlist) { a.wish++; return; }
      a.cost += d.cost; a.subs += d.subCount;
      if (d.noData || d.daysLeft == null) a.nodata++;
      else if (d.daysLeft < 0) a.expired++;
      else if (d.daysLeft < 7) a.crit++;
      else if (d.daysLeft < 30) a.soon++;
      else a.ok++;
      if (!d.notify.expiry) a.silent++;
      if (d.ssl && d.ssl.daysLeft < 0) a.sslExp++;
      else if (d.ssl && d.ssl.daysLeft < 90) a.ssl90++;
      if (!d.email || !d.email.dmarc || d.email.dmarc === 'none') a.noDmarc++;
      a.health += d.health;
    });
    a.avgHealth = Math.round(a.health / Math.max(1, domains.length - a.wish));
    return a;
  }, [domains]);

  const tracked = agg.total - agg.wish;
  const dist = [
    { k: 'green', label: 'В норме (> 30 дней)', n: agg.ok, col: 'var(--pv-green)' },
    { k: 'gold', label: 'Истекают (7–30 дней)', n: agg.soon, col: 'var(--pv-gold)' },
    { k: 'red', label: 'Критично (< 7 дней)', n: agg.crit, col: 'var(--pv-orange)' },
    { k: 'red2', label: 'Истекли', n: agg.expired, col: 'var(--pv-red)' },
    { k: 'gray', label: 'Без данных', n: agg.nodata, col: 'var(--pv-fg-subtle)' },
  ];
  const maxDist = Math.max(...dist.map(x => x.n), 1);

  const topRisks = useMemo(() =>
    domains.filter(d => !d.isWishlist).slice().sort((a,b) => a.health - b.health).slice(0, 5)
  , [domains]);

  // group spend breakdown
  const byGroup = useMemo(() => {
    const m = {};
    domains.forEach(d => { if (d.isWishlist) return; const g = d.groups[0] || '_none'; m[g] = (m[g] || 0) + d.cost; });
    return Object.entries(m).map(([id, cost]) => ({ id, cost, g: groupById(id) })).sort((a,b) => b.cost - a.cost).slice(0, 5);
  }, [domains]);
  const maxGroup = Math.max(...byGroup.map(x => x.cost), 1);

  const money = n => n.toLocaleString('ru-RU') + ' ₽';

  return (
    <div className="tg-pad tg-pad-b">
      {/* hero health */}
      <div className="tg-card" style={{ padding: 18, display: 'flex', alignItems: 'center', gap: 18 }}>
        <Ring value={agg.avgHealth} size={92} stroke={9} label="из 100" />
        <div style={{ flex: 1 }}>
          <div className="tg-kpi-lbl" style={{ marginBottom: 4 }}>Здоровье портфеля</div>
          <div style={{ fontSize: 15, color: 'var(--pv-fg-body)', lineHeight: 1.4 }}>
            {agg.avgHealth >= 75 ? 'Портфель в хорошем состоянии.' : agg.avgHealth >= 50 ? 'Есть домены, требующие внимания.' : 'Много рисков — проверьте критичные.'}
          </div>
          {(agg.crit + agg.expired) > 0 && (
            <button className="pv-btn pv-btn-sm pv-btn-danger" style={{ marginTop: 10 }} onClick={() => go({ tab: 'list', filter: 'crit' })}>
              <Icon name="priority_high" />{agg.crit + agg.expired} требуют действий
            </button>
          )}
        </div>
      </div>

      {/* KPIs */}
      <div className="tg-kpis" style={{ marginTop: 12 }}>
        <div className="tg-kpi" onClick={() => go({ tab: 'list', filter: 'all' })}>
          <div className="tg-kpi-lbl"><Icon name="language" />Доменов</div>
          <div className="tg-kpi-val">{tracked}</div>
          <div className="tg-kpi-sub">+{12} за месяц</div>
        </div>
        <div className="tg-kpi" onClick={() => go({ tab: 'list', filter: 'soon' })}>
          <div className="tg-kpi-lbl"><Icon name="hourglass_bottom" />Истекают &lt; 30 дн.</div>
          <div className="tg-kpi-val" style={{ color: agg.soon + agg.crit > 0 ? 'var(--pv-gold)' : undefined }}>{agg.soon + agg.crit}</div>
          <div className="tg-kpi-sub">{agg.crit} критичных</div>
        </div>
        <div className="tg-kpi" onClick={() => go({ tab: 'list', filter: 'problem' })}>
          <div className="tg-kpi-lbl"><Icon name="lock_clock" />SSL &lt; 90 дн.</div>
          <div className="tg-kpi-val">{agg.ssl90 + agg.sslExp}</div>
          <div className="tg-kpi-sub">{agg.sslExp} истекли</div>
        </div>
        <div className="tg-kpi" onClick={() => go({ tab: 'list', filter: 'silent' })}>
          <div className="tg-kpi-lbl"><Icon name="mark_email_unread" />Без DMARC</div>
          <div className="tg-kpi-val">{agg.noDmarc}</div>
          <div className="tg-kpi-sub">риск спуфинга</div>
        </div>
      </div>

      {/* distribution */}
      <div className="tg-card" style={{ marginTop: 12, padding: 16 }}>
        <div className="tg-card-title" style={{ padding: 0, marginBottom: 14 }}><Icon name="donut_small" />Распределение по сроку</div>
        <div className="tg-distbar">
          {dist.map(x => x.n > 0 && <i key={x.k} style={{ width: (x.n / tracked * 100) + '%', background: x.col }} />)}
        </div>
        <div className="tg-legend">
          {dist.map(x => (
            <div key={x.k} className="tg-legend-row">
              <span className="tg-lg-dot" style={{ background: x.col }} />
              <span>{x.label}</span>
              <span className="tg-lg-bar"><i style={{ width: (x.n / maxDist * 100) + '%', background: x.col }} /></span>
              <span className="tg-lg-n">{x.n}</span>
            </div>
          ))}
        </div>
      </div>

      {/* budget */}
      <div className="tg-card" style={{ marginTop: 12, padding: 16 }}>
        <div className="tg-card-title" style={{ padding: 0, marginBottom: 12 }}><Icon name="payments" />Бюджет продления<span className="tg-ct-action" onClick={() => go({ tab: 'calendar' })}>календарь →</span></div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 4 }}>
          <div style={{ fontSize: 30, fontWeight: 700, color: 'var(--pv-fg)', fontVariantNumeric: 'tabular-nums' }}>{money(agg.cost)}</div>
          <div style={{ fontSize: 13, color: 'var(--pv-fg-muted)' }}>в год</div>
        </div>
        <div style={{ fontSize: 13, color: 'var(--pv-fg-muted)', marginBottom: 14 }}>
          Ближайшие 30 дней: <b style={{ color: 'var(--pv-fg)' }}>{money(domains.filter(d => !d.isWishlist && d.daysLeft != null && d.daysLeft < 30).reduce((s, d) => s + d.cost, 0))}</b>
        </div>
        <div className="tg-legend">
          {byGroup.map(x => (
            <div key={x.id} className="tg-legend-row">
              <span className="tg-lg-dot" style={{ background: x.g ? avatarHue(x.g.color) : 'var(--pv-fg-subtle)' }} />
              <span>{x.g ? x.g.name : 'Без группы'}</span>
              <span className="tg-lg-bar"><i style={{ width: (x.cost / maxGroup * 100) + '%', background: x.g ? avatarHue(x.g.color) : 'var(--pv-fg-subtle)' }} /></span>
              <span className="tg-lg-n">{money(x.cost)}</span>
            </div>
          ))}
        </div>
      </div>

      {/* top risks */}
      <div className="tg-card" style={{ marginTop: 12 }}>
        <div className="tg-card-title"><Icon name="warning" />Топ-риски<span className="tg-ct-action" onClick={() => go({ tab: 'list', sort: 'health' })}>все →</span></div>
        {topRisks.map(d => {
          const s = statusOf(d);
          return (
            <div key={d.id} className="tg-irow tap" onClick={() => onOpen(d)}>
              <Ring value={d.health} size={34} stroke={4} showLabel={false} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--pv-fg)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.name}</div>
                <div style={{ fontSize: 12, color: s.dot }}>{daysText(d)}</div>
              </div>
              <Icon name="chevron_right" style={{ color: 'var(--pv-fg-subtle)' }} />
            </div>
          );
        })}
      </div>
    </div>
  );
}

Object.assign(window, { DashboardScreen });
