/* ============================================================
   Карточка домена — вкладки Обзор / WHOIS / SSL / DNS / Email /
   Поддомены, health-score, лента изменений.
   ============================================================ */
function DomainScreen({ d, onAction, toast, setDomain }) {
  const [tab, setTab] = useState('overview');
  const s = statusOf(d);
  const history = window.DATA.historyFor(d);

  const TABS = [
    { id: 'overview', label: 'Обзор', icon: 'donut_large' },
    { id: 'whois', label: 'WHOIS', icon: 'badge' },
    { id: 'ssl', label: 'SSL', icon: 'lock', dot: d.ssl ? (d.ssl.daysLeft < 0 ? 'var(--pv-red)' : d.ssl.daysLeft < 14 ? 'var(--pv-gold)' : null) : 'var(--pv-fg-subtle)' },
    { id: 'dns', label: 'DNS', icon: 'dns' },
    { id: 'email', label: 'Email', icon: 'mail', dot: d.email && !d.email.dmarc ? 'var(--pv-gold)' : null },
    { id: 'subs', label: 'Поддомены', icon: 'lan' },
  ];

  return (
    <>
      <div className="tg-ctabs">
        {TABS.map(t => (
          <button key={t.id} className={"tg-ctab" + (tab === t.id ? " active" : "")} onClick={() => setTab(t.id)}>
            <Icon name={t.icon} />{t.label}
            {t.id === 'subs' && d.subCount > 0 && <span style={{ fontSize: 11, color: 'var(--pv-fg-subtle)' }}>{d.subCount}</span>}
            {t.dot && <span className="tg-ctab-dot" style={{ background: t.dot }} />}
          </button>
        ))}
      </div>

      <div className="tg-pad tg-pad-b">
        {tab === 'overview' && <OverviewTab d={d} s={s} history={history} onAction={onAction} setDomain={setDomain} toast={toast} />}
        {tab === 'whois' && <WhoisTab d={d} />}
        {tab === 'ssl' && <SslTab d={d} />}
        {tab === 'dns' && <DnsTab d={d} />}
        {tab === 'email' && <EmailTab d={d} />}
        {tab === 'subs' && <SubsTab d={d} toast={toast} />}
      </div>
    </>
  );
}

function OverviewTab({ d, s, history, onAction, setDomain, toast }) {
  const toggle = (key) => {
    setDomain({ ...d, notify: { ...d.notify, [key]: !d.notify[key] } });
    toast(d.notify[key] ? 'Уведомление выключено' : 'Уведомление включено', 'notifications');
  };
  return (
    <>
      {/* hero */}
      <div className="tg-card" style={{ padding: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <Ring value={d.health} size={72} stroke={7} label="health" />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
              <span className="tg-pill" style={{ background: s.dot + '22', color: s.dot }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: s.dot }} />{s.label}
              </span>
            </div>
            <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--pv-fg)', lineHeight: 1.2 }}>{daysText(d)}</div>
            <div style={{ fontSize: 13, color: 'var(--pv-fg-muted)', marginTop: 2 }}>до {d.expires || 'нет данных'}</div>
          </div>
        </div>
        {d.groups.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 14 }}>
            {d.groups.map(g => <GroupTag key={g} id={g} />)}
            <span className="tg-mini-tag" style={{ background: 'var(--pv-muted)', color: 'var(--pv-fg-muted)', display: 'inline-flex', alignItems: 'center', gap: 3 }}>
              <Icon name="add" style={{ fontSize: 11 }} />тег
            </span>
          </div>
        )}
      </div>

      {/* quick actions */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginTop: 12 }}>
        <QuickAct icon="refresh" label="Обновить" onClick={() => onAction('refresh')} />
        <QuickAct icon="content_copy" label="Полный WHOIS" onClick={() => onAction('raw')} />
        <QuickAct icon="ios_share" label="Поделиться" onClick={() => onAction('share')} />
      </div>

      {/* health breakdown */}
      <div className="tg-card" style={{ marginTop: 12 }}>
        <div className="tg-card-title"><Icon name="monitor_heart" />Из чего складывается health-score</div>
        <HealthFactor ok={d.daysLeft == null ? false : d.daysLeft > 30} label="Срок регистрации" val={d.daysLeft == null ? 'нет данных' : daysText(d)} />
        <HealthFactor ok={d.ssl && d.ssl.daysLeft > 14} warn={d.ssl && d.ssl.daysLeft >= 0 && d.ssl.daysLeft <= 14} label="SSL-сертификат" val={d.ssl ? (d.ssl.daysLeft < 0 ? 'истёк' : `${d.ssl.daysLeft} дн.`) : 'нет'} />
        <HealthFactor ok={d.email && !!d.email.dmarc && d.email.dmarc !== 'none'} warn={d.email && d.email.dmarc === 'none'} label="DMARC-политика" val={d.email && d.email.dmarc ? d.email.dmarc : 'нет'} />
        <HealthFactor ok={d.dns && d.dns.dnssec} label="DNSSEC" val={d.dns && d.dns.dnssec ? 'включён' : 'выключен'} />
        <HealthFactor ok={!d.flags.some(f => ['clientHold','pendingDelete','redemptionPeriod'].includes(f))} label="Статусы домена" val={d.flags.some(f => ['clientHold','pendingDelete','redemptionPeriod'].includes(f)) ? 'проблема' : 'чисто'} />
      </div>

      {/* notifications */}
      <div className="tg-card" style={{ marginTop: 12 }}>
        <div className="tg-card-title"><Icon name="notifications" />Уведомления</div>
        <NotifyRow label="Истечение регистрации" sub="за 30, 7 и 1 день" on={d.notify.expiry} onToggle={() => toggle('expiry')} />
        <NotifyRow label="Смена NS-серверов" on={d.notify.ns} onToggle={() => toggle('ns')} />
        <NotifyRow label="Смена регистратора" on={d.notify.registrar} onToggle={() => toggle('registrar')} />
        <NotifyRow label="Изменение статусов" on={d.notify.status} onToggle={() => toggle('status')} />
      </div>

      {/* history / change feed */}
      <div className="tg-card" style={{ marginTop: 12 }}>
        <div className="tg-card-title"><Icon name="history" />Лента изменений</div>
        {history.map((h, i) => (
          <div key={i} className="tg-irow" style={{ alignItems: 'flex-start' }}>
            <div className="tg-ir-ico"><Icon name={h.icon} style={{ color: h.sev === 'success' ? 'var(--pv-green)' : h.sev === 'info' ? 'var(--pv-blue)' : 'var(--pv-fg-muted)' }} /></div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 14, color: 'var(--pv-fg)' }}>{h.text}</div>
              <div style={{ fontSize: 11, color: 'var(--pv-fg-subtle)', marginTop: 2 }}>{h.when}</div>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

const QuickAct = ({ icon, label, onClick }) => (
  <button onClick={onClick} style={{ border: '1px solid var(--pv-border)', background: 'var(--pv-panel)', borderRadius: 12, padding: '12px 6px', cursor: 'pointer', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5, fontFamily: 'inherit' }}>
    <Icon name={icon} style={{ fontSize: 22, color: 'var(--pv-cta)' }} />
    <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--pv-fg-body)' }}>{label}</span>
  </button>
);

const HealthFactor = ({ ok, warn, label, val }) => (
  <div className="tg-irow">
    <Icon name={warn ? 'warning' : ok ? 'check_circle' : 'cancel'} style={{ fontSize: 20, color: warn ? 'var(--pv-gold)' : ok ? 'var(--pv-green)' : 'var(--pv-red)' }} />
    <div className="tg-ir-label" style={{ color: 'var(--pv-fg-body)', flex: 1 }}>{label}</div>
    <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--pv-fg-muted)' }}>{val}</div>
  </div>
);

const NotifyRow = ({ label, sub, on, onToggle }) => (
  <div className="tg-irow">
    <div style={{ flex: 1 }}>
      <div style={{ fontSize: 14, color: 'var(--pv-fg)', fontWeight: 700 }}>{label}</div>
      {sub && <div style={{ fontSize: 12, color: 'var(--pv-fg-muted)', marginTop: 1 }}>{sub}</div>}
    </div>
    <div className={"pv-toggle" + (on ? " on" : "")} onClick={onToggle} />
  </div>
);

// ── WHOIS tab ───────────────────────────────────────────────
function WhoisTab({ d }) {
  if (d.noData) return <NoData label="WHOIS-данные ещё подгружаются" />;
  return (
    <>
      <div className="tg-card">
        <div className="tg-card-title"><Icon name="event" />Срок действия</div>
        <IRow icon="play_circle" label="Зарегистрирован" value={d.registered} />
        <IRow icon="event_busy" label="Истекает" value={d.expires} />
        <IRow icon="update" label="Обновлён" value={d.updated} />
      </div>
      <div className="tg-card">
        <div className="tg-card-title"><Icon name="corporate_fare" />Регистратор</div>
        <IRow icon="business" label="Регистратор" value={d.registrar} />
        <IRow icon="link" label="Сайт" value={<span className="pv-mono" style={{ fontWeight: 400, fontSize: 13 }}>{d.registrarHost}</span>} />
      </div>
      <div className="tg-card">
        <div className="tg-card-title"><Icon name="shield" />Статусы домена</div>
        <div style={{ padding: '4px 14px 14px', display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {d.flags.map(f => {
            const bad = ['clientHold','pendingDelete','redemptionPeriod'].includes(f);
            return <span key={f} className="tg-mini-tag" style={{ fontSize: 12, padding: '4px 10px', background: bad ? 'rgba(230,64,58,0.12)' : 'var(--pv-muted)', color: bad ? 'var(--pv-red)' : 'var(--pv-fg-body)' }}>{f}</span>;
          })}
        </div>
      </div>
      {d.dns && (
        <div className="tg-card">
          <div className="tg-card-title"><Icon name="dns" />NS-серверы</div>
          {d.dns.ns.map((n, i) => <IRow key={i} icon={i === 0 ? 'lan' : null} value={<span className="pv-mono" style={{ fontWeight: 400, fontSize: 13 }}>{n}</span>} />)}
        </div>
      )}
      <div className="tg-hint">Данные получены: {d.lastCheck}. Авто-проверка идёт по расписанию, обновить вручную — кнопкой внизу.</div>
    </>
  );
}

// ── SSL tab ─────────────────────────────────────────────────
function SslTab({ d }) {
  if (!d.ssl) return <NoData label="SSL-сертификат не обнаружен" icon="lock_open" hint="HTTPS не настроен или сайт недоступен." />;
  const ssl = d.ssl;
  const warn = ssl.daysLeft >= 0 && ssl.daysLeft <= 14;
  const bad = ssl.daysLeft < 0;
  return (
    <>
      <div className="tg-card" style={{ padding: 16, display: 'flex', alignItems: 'center', gap: 14 }}>
        <div className="tg-alert-ico" style={{ width: 48, height: 48, borderRadius: 12, background: bad ? 'rgba(230,64,58,0.12)' : warn ? 'rgba(244,185,33,0.16)' : 'rgba(41,180,115,0.12)', color: bad ? 'var(--pv-red)' : warn ? '#b07d00' : 'var(--pv-green-2)' }}>
          <Icon name={bad ? 'lock_open' : 'lock'} style={{ fontSize: 26 }} />
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--pv-fg)' }}>{bad ? 'Сертификат истёк' : `Действует ещё ${ssl.daysLeft} дн.`}</div>
          <div style={{ fontSize: 13, color: 'var(--pv-fg-muted)' }}>до {ssl.validTo}</div>
        </div>
        <div style={{ fontSize: 22, fontWeight: 700, color: bad ? 'var(--pv-red)' : 'var(--pv-green-2)' }}>{ssl.grade === 'expired' ? '—' : ssl.grade}</div>
      </div>
      <div className="tg-card">
        <div className="tg-card-title"><Icon name="verified" />Сертификат</div>
        <IRow icon="badge" label="Издатель" value={ssl.issuer} />
        <IRow icon="enhanced_encryption" label="Протокол" value={ssl.tls} />
        <IRow icon="grade" label="Оценка" value={ssl.grade === 'expired' ? 'истёк' : ssl.grade} />
        <IRow icon="event_busy" label="Действует до" value={ssl.validTo} />
      </div>
      <div className="tg-hint">Бот отслеживает истечение сертификата и предупредит за 14 и 3 дня.</div>
    </>
  );
}

// ── DNS tab ─────────────────────────────────────────────────
function DnsTab({ d }) {
  if (!d.dns) return <NoData label="DNS-записи недоступны" icon="dns" />;
  const dns = d.dns;
  return (
    <>
      <div className="tg-card">
        <div className="tg-card-title"><Icon name="dns" />A / AAAA записи</div>
        {dns.a.map((ip, i) => <IRow key={'a'+i} icon={i === 0 ? 'public' : null} label="A" value={<span className="pv-mono" style={{ fontWeight: 400, fontSize: 13 }}>{ip}</span>} />)}
        {dns.aaaa.map((ip, i) => <IRow key={'aaaa'+i} label="AAAA" value={<span className="pv-mono" style={{ fontWeight: 400, fontSize: 12 }}>{ip}</span>} />)}
        {dns.aaaa.length === 0 && <IRow label="AAAA" value={<span style={{ color: 'var(--pv-fg-subtle)' }}>нет IPv6</span>} />}
      </div>
      <div className="tg-card">
        <div className="tg-card-title"><Icon name="hub" />Инфраструктура</div>
        <IRow icon="cloud" label="Провайдер NS" value={dns.provider} />
        <IRow icon="router" label="ASN" value={<span>{dns.asn} · {dns.asnOrg}</span>} />
        <IRow icon="security" label="DNSSEC" value={<Check ok={dns.dnssec}>{dns.dnssec ? 'включён' : 'выключен'}</Check>} />
      </div>
      <div className="tg-card">
        <div className="tg-card-title"><Icon name="lan" />NS-серверы</div>
        {dns.ns.map((n, i) => <IRow key={i} value={<span className="pv-mono" style={{ fontWeight: 400, fontSize: 13 }}>{n}</span>} />)}
      </div>
    </>
  );
}

// ── Email tab ───────────────────────────────────────────────
function EmailTab({ d }) {
  if (!d.email) return <NoData label="Почтовые записи не найдены" icon="mail" />;
  const e = d.email;
  return (
    <>
      <div className="tg-card">
        <div className="tg-card-title"><Icon name="alternate_email" />Почтовый провайдер</div>
        <IRow icon="mail" label="MX" value={e.mx} />
      </div>
      <div className="tg-card">
        <div className="tg-card-title"><Icon name="shield_lock" />Защита от спуфинга</div>
        <IRow icon="task_alt" label="SPF" value={<Check ok={e.spf}>{e.spf ? 'настроен' : 'отсутствует'}</Check>} />
        <IRow icon="key" label="DKIM" value={<Check ok={e.dkim}>{e.dkim ? 'настроен' : 'отсутствует'}</Check>} />
        <IRow icon="policy" label="DMARC" value={<Check ok={e.dmarc && e.dmarc !== 'none'} warn={e.dmarc === 'none'}>{e.dmarc ? `p=${e.dmarc}` : 'отсутствует'}</Check>} />
      </div>
      {(!e.dmarc || e.dmarc === 'none') && (
        <div className="tg-card" style={{ padding: 14, display: 'flex', gap: 10, alignItems: 'flex-start' }}>
          <Icon name="lightbulb" style={{ color: 'var(--pv-gold)', fontSize: 20 }} />
          <div style={{ fontSize: 13, color: 'var(--pv-fg-body)', lineHeight: 1.45 }}>
            Рекомендуем настроить DMARC с политикой <b>quarantine</b> или <b>reject</b> — это защитит домен от подделки писем.
          </div>
        </div>
      )}
    </>
  );
}

// ── Subdomains tab ──────────────────────────────────────────
function SubsTab({ d, toast }) {
  const subs = useMemo(() => {
    const labels = ['www','api','app','mail','cdn','blog','shop','lk','admin','dev','stage','m','static','img','vpn','git','ftp','db','status','docs','help','support','my','cloud','test','beta','old','new','assets','media'];
    const n = Math.min(d.subCount, 30);
    return labels.slice(0, n).map((l, i) => ({ name: l + '.' + d.name, tracked: i < 2, fresh: i === 0 }));
  }, [d]);
  if (d.subCount === 0) return <NoData label="Поддомены не найдены" icon="lan" hint="Поиск идёт через CT-логи crt.sh. Попробуйте обновить позже." />;
  return (
    <>
      <div className="tg-card" style={{ padding: 14, display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13, color: 'var(--pv-fg-muted)' }}>Найдено через crt.sh</div>
          <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--pv-fg)' }}>{d.subCount} {plural(d.subCount, 'поддомен', 'поддомена', 'поддоменов')}</div>
        </div>
        <button className="pv-btn pv-btn-sm" onClick={() => toast('Все поддомены добавлены на слежение', 'check_circle')}>
          <Icon name="visibility" />Следить за всеми
        </button>
      </div>
      <div className="tg-card" style={{ marginTop: 12 }}>
        {subs.map((sub, i) => (
          <div key={i} className="tg-irow">
            <Icon name="subdirectory_arrow_right" style={{ fontSize: 18, color: 'var(--pv-fg-subtle)' }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="pv-mono" style={{ fontSize: 14, color: 'var(--pv-fg)', overflow: 'hidden', textOverflow: 'ellipsis' }}>{sub.name}</div>
            </div>
            {sub.fresh && <span className="tg-mini-tag" style={{ background: 'rgba(54,169,225,0.14)', color: 'var(--pv-blue-3)' }}>новый</span>}
            {sub.tracked
              ? <span className="tg-pill" style={{ background: 'rgba(41,180,115,0.12)', color: 'var(--pv-green-2)' }}><Icon name="visibility" style={{ fontSize: 13 }} />слежу</span>
              : <button className="pv-btn pv-btn-sm" onClick={() => toast(sub.name + ' добавлен', 'check_circle')} style={{ height: 26 }}><Icon name="add" />Следить</button>}
          </div>
        ))}
      </div>
    </>
  );
}

const NoData = ({ label, icon = 'hourglass_empty', hint }) => (
  <div className="tg-empty2" style={{ padding: '50px 30px' }}>
    <Icon name={icon} /><b>{label}</b>
    {hint && <div style={{ fontSize: 13 }}>{hint}</div>}
  </div>
);

Object.assign(window, { DomainScreen });
