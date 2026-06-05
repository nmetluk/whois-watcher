/* eslint-disable @typescript-eslint/no-explicit-any */
/* Карточка домена — порт design/webapp/v1/app/screen-domain.jsx (TASK-0087).
   Отличия от прототипа: данные из /api/webapp/domain/{id}; «Лента изменений»
   опущена (на бэкенде нет источника истории); поддомены — реальные имена
   из subdomain_enum_cache. */
import React, { useEffect, useMemo, useState } from 'react';
import { Icon } from '../components/Icon';
import { Ring } from '../components/Ring';
import { IRow } from '../components/IRow';
import { Check } from '../components/Check';
import { GroupTag } from '../components/GroupTag';
import { statusOf, daysText } from '../lib/domain';
import { api, fetchDomain, addDomain } from '../lib/api';

const BAD_FLAGS = ['clientHold', 'pendingDelete', 'redemptionPeriod'];

function plural(n: number, one: string, few: string, many: string): string {
  const m10 = n % 10, m100 = n % 100;
  if (m10 === 1 && m100 !== 11) return one;
  if (m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20)) return few;
  return many;
}

const NoData: React.FC<{label:string; icon?:string; hint?:string}> = ({ label, icon = 'hourglass_empty', hint }) => (
  <div className="tg-empty2" style={{ padding: '50px 30px' }}>
    <Icon name={icon} /><b>{label}</b>
    {hint && <div style={{ fontSize: 13 }}>{hint}</div>}
  </div>
);

const QuickAct: React.FC<any> = ({ icon, label, onClick }) => (
  <button onClick={onClick} style={{ border: '1px solid var(--pv-border)', background: 'var(--pv-panel)', borderRadius: 12, padding: '12px 6px', cursor: 'pointer', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5, fontFamily: 'inherit' }}>
    <Icon name={icon} style={{ fontSize: 22, color: 'var(--pv-cta)' }} />
    <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--pv-fg-body)' }}>{label}</span>
  </button>
);

const HealthFactor: React.FC<any> = ({ ok, warn, label, val }) => (
  <div className="tg-irow">
    <Icon name={warn ? 'warning' : ok ? 'check_circle' : 'cancel'} style={{ fontSize: 20, color: warn ? 'var(--pv-gold)' : ok ? 'var(--pv-green)' : 'var(--pv-red)' }} />
    <div className="tg-ir-label" style={{ color: 'var(--pv-fg-body)', flex: 1 }}>{label}</div>
    <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--pv-fg-muted)' }}>{val}</div>
  </div>
);

const NotifyRow: React.FC<any> = ({ label, sub, on, onToggle }) => (
  <div className="tg-irow">
    <div style={{ flex: 1 }}>
      <div style={{ fontSize: 14, color: 'var(--pv-fg)', fontWeight: 700 }}>{label}</div>
      {sub && <div style={{ fontSize: 12, color: 'var(--pv-fg-muted)', marginTop: 1 }}>{sub}</div>}
    </div>
    <div className={'pv-toggle' + (on ? ' on' : '')} onClick={onToggle} />
  </div>
);

const Mono: React.FC<{children:React.ReactNode; size?:number}> = ({ children, size = 13 }) => (
  <span className="pv-mono" style={{ fontWeight: 400, fontSize: size }}>{children}</span>
);

export const DomainScreen: React.FC<any> = ({ d: initial, onBack: _onBack, toast }) => {
  const [tab, setTab] = useState('overview');
  const [d, setD] = useState<any>(initial);
  const [showRaw, setShowRaw] = useState(false);

  const reload = React.useCallback(() => {
    if (!initial?.id) return;
    fetchDomain(initial.id).then(setD).catch(() => toast('Не удалось обновить', 'error'));
  }, [initial?.id, toast]);

  useEffect(() => { reload(); }, [reload]);

  if (!d) return <NoData label="Домен не найден" icon="error" />;
  const s = statusOf(d);

  const TABS = [
    { id: 'overview', label: 'Обзор', icon: 'donut_large', dot: null as string | null },
    { id: 'whois', label: 'WHOIS', icon: 'badge', dot: null },
    { id: 'ssl', label: 'SSL', icon: 'lock', dot: d.ssl ? (d.ssl.daysLeft < 0 ? 'var(--pv-red)' : d.ssl.daysLeft < 14 ? 'var(--pv-gold)' : null) : 'var(--pv-fg-subtle)' },
    { id: 'dns', label: 'DNS', icon: 'dns', dot: null },
    { id: 'email', label: 'Email', icon: 'mail', dot: d.email && !d.email.dmarc ? 'var(--pv-gold)' : null },
    { id: 'subs', label: 'Поддомены', icon: 'lan', dot: null },
  ];

  const toggle = (key: string) => {
    const next = !d.notify?.[key];
    setD({ ...d, notify: { ...d.notify, [key]: next } }); // оптимистично
    api.post(`/domain/${d.id}/toggle`, { key, enabled: next })
      .then(() => toast(next ? 'Уведомление включено' : 'Уведомление выключено', 'notifications'))
      .catch(() => { setD((p: any) => ({ ...p, notify: { ...p.notify, [key]: !next } })); toast('Не удалось сохранить', 'error'); });
  };

  const share = async () => {
    const text = `${d.unicode || d.name} — ${daysText(d)}${d.expires ? ` (до ${d.expires})` : ''}`;
    try {
      if (navigator.share) await navigator.share({ text });
      else { await navigator.clipboard.writeText(text); toast('Скопировано', 'content_copy'); }
    } catch { /* отменено пользователем */ }
  };

  return <>
    <div className="tg-ctabs">
      {TABS.map(t => (
        <button key={t.id} className={'tg-ctab' + (tab === t.id ? ' active' : '')} onClick={() => setTab(t.id)}>
          <Icon name={t.icon} />{t.label}
          {t.id === 'subs' && d.subCount > 0 && <span style={{ fontSize: 11, color: 'var(--pv-fg-subtle)' }}>{d.subCount}</span>}
          {t.dot && <span className="tg-ctab-dot" style={{ background: t.dot }} />}
        </button>
      ))}
    </div>

    <div className="tg-pad tg-pad-b">
      {tab === 'overview' && <>
        <div className="tg-card" style={{ padding: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <Ring value={d.health ?? 0} size={72} stroke={7} label="health" />
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
          {(d.groups?.length ?? 0) > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 14 }}>
              {d.groups.map((g: any) => <GroupTag key={g} id={String(g)} />)}
            </div>
          )}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginTop: 12 }}>
          <QuickAct icon="refresh" label="Обновить" onClick={() => { reload(); toast('Обновлено из кэша', 'refresh'); }} />
          <QuickAct icon="content_copy" label="Полный WHOIS" onClick={() => { setTab('whois'); setShowRaw(true); }} />
          <QuickAct icon="ios_share" label="Поделиться" onClick={share} />
        </div>

        <div className="tg-card" style={{ marginTop: 12 }}>
          <div className="tg-card-title"><Icon name="monitor_heart" />Из чего складывается health-score</div>
          <HealthFactor ok={d.daysLeft != null && d.daysLeft > 30} label="Срок регистрации" val={d.daysLeft == null ? 'нет данных' : daysText(d)} />
          <HealthFactor ok={d.ssl && d.ssl.daysLeft > 14} warn={d.ssl && d.ssl.daysLeft >= 0 && d.ssl.daysLeft <= 14} label="SSL-сертификат" val={d.ssl ? (d.ssl.daysLeft < 0 ? 'истёк' : `${d.ssl.daysLeft} дн.`) : 'нет'} />
          <HealthFactor ok={d.email && !!d.email.dmarc && d.email.dmarc !== 'none'} warn={d.email && d.email.dmarc === 'none'} label="DMARC-политика" val={d.email?.dmarc || 'нет'} />
          <HealthFactor ok={d.dns?.dnssec} label="DNSSEC" val={d.dns?.dnssec ? 'включён' : 'выключен'} />
          <HealthFactor ok={!(d.flags || []).some((f: string) => BAD_FLAGS.includes(f))} label="Статусы домена" val={(d.flags || []).some((f: string) => BAD_FLAGS.includes(f)) ? 'проблема' : 'чисто'} />
        </div>

        <div className="tg-card" style={{ marginTop: 12 }}>
          <div className="tg-card-title"><Icon name="notifications" />Уведомления</div>
          <NotifyRow label="Истечение регистрации" sub="за 30, 7 и 1 день" on={d.notify?.expiry} onToggle={() => toggle('expiry')} />
          <NotifyRow label="Смена NS-серверов" on={d.notify?.ns} onToggle={() => toggle('ns')} />
          <NotifyRow label="Смена регистратора" on={d.notify?.registrar} onToggle={() => toggle('registrar')} />
          <NotifyRow label="Изменение статусов" on={d.notify?.status} onToggle={() => toggle('status')} />
        </div>
      </>}

      {tab === 'whois' && (d.noData ? <NoData label="WHOIS-данные ещё подгружаются" /> : <>
        <div className="tg-card">
          <div className="tg-card-title"><Icon name="event" />Срок действия</div>
          <IRow icon="play_circle" label="Зарегистрирован" value={d.registered || '—'} />
          <IRow icon="event_busy" label="Истекает" value={d.expires || '—'} />
          <IRow icon="update" label="Обновлён" value={d.updated || '—'} />
        </div>
        <div className="tg-card">
          <div className="tg-card-title"><Icon name="corporate_fare" />Регистратор</div>
          <IRow icon="business" label="Регистратор" value={d.registrar || '—'} />
          {d.registrarHost && <IRow icon="link" label="Сайт" value={<Mono>{d.registrarHost}</Mono>} />}
        </div>
        {(d.flags?.length ?? 0) > 0 && <div className="tg-card">
          <div className="tg-card-title"><Icon name="shield" />Статусы домена</div>
          <div style={{ padding: '4px 14px 14px', display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {d.flags.map((f: string) => {
              const bad = BAD_FLAGS.includes(f);
              return <span key={f} className="tg-mini-tag" style={{ fontSize: 12, padding: '4px 10px', background: bad ? 'rgba(230,64,58,0.12)' : 'var(--pv-muted)', color: bad ? 'var(--pv-red)' : 'var(--pv-fg-body)' }}>{f}</span>;
            })}
          </div>
        </div>}
        {d.dns?.ns?.length > 0 && <div className="tg-card">
          <div className="tg-card-title"><Icon name="dns" />NS-серверы</div>
          {d.dns.ns.map((n: string, i: number) => <IRow key={i} icon={i === 0 ? 'lan' : undefined} value={<Mono>{n}</Mono>} />)}
        </div>}
        {showRaw && d.rawWhoisSample && <div className="tg-card">
          <div className="tg-card-title"><Icon name="data_object" />Сырой WHOIS</div>
          <pre style={{ margin: 0, padding: '4px 14px 14px', fontSize: 11, whiteSpace: 'pre-wrap', wordBreak: 'break-all', color: 'var(--pv-fg-body)' }}>{d.rawWhoisSample}</pre>
        </div>}
        {!showRaw && d.rawWhoisSample && <button className="pv-btn" style={{ width: '100%', justifyContent: 'center', marginTop: 12 }} onClick={() => setShowRaw(true)}><Icon name="data_object" />Показать сырой WHOIS</button>}
        <div className="tg-hint">Данные получены: {d.lastCheck}. Авто-проверка идёт по расписанию.</div>
      </>)}

      {tab === 'ssl' && (!d.ssl ? <NoData label="SSL-сертификат не обнаружен" icon="lock_open" hint="HTTPS не настроен или сайт недоступен." /> : (() => {
        const ssl = d.ssl;
        const warn = ssl.daysLeft >= 0 && ssl.daysLeft <= 14;
        const bad = ssl.daysLeft < 0;
        return <>
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
            <IRow icon="grade" label="Оценка" value={ssl.grade === 'expired' ? 'истёк' : ssl.grade} />
            <IRow icon="event_busy" label="Действует до" value={ssl.validTo} />
          </div>
          <div className="tg-hint">Бот отслеживает истечение сертификата и предупредит по вашим настройкам SSL-напоминаний.</div>
        </>;
      })())}

      {tab === 'dns' && (!d.dns ? <NoData label="DNS-записи недоступны" icon="dns" /> : <>
        <div className="tg-card">
          <div className="tg-card-title"><Icon name="dns" />A / AAAA записи</div>
          {(d.dns.a || []).map((ip: string, i: number) => <IRow key={'a' + i} icon={i === 0 ? 'public' : undefined} label="A" value={<Mono>{ip}</Mono>} />)}
          {(d.dns.aaaa || []).map((ip: string, i: number) => <IRow key={'aaaa' + i} label="AAAA" value={<Mono size={12}>{ip}</Mono>} />)}
          {(d.dns.aaaa || []).length === 0 && <IRow label="AAAA" value={<span style={{ color: 'var(--pv-fg-subtle)' }}>нет IPv6</span>} />}
        </div>
        <div className="tg-card">
          <div className="tg-card-title"><Icon name="hub" />Инфраструктура</div>
          {d.dns.asn && <IRow icon="router" label="ASN" value={<span>AS{d.dns.asn}{d.dns.asnOrg ? ` · ${d.dns.asnOrg}` : ''}</span>} />}
          <IRow icon="security" label="DNSSEC" value={<Check ok={d.dns.dnssec}>{d.dns.dnssec ? 'включён' : 'выключен'}</Check>} />
        </div>
        {(d.dns.ns || []).length > 0 && <div className="tg-card">
          <div className="tg-card-title"><Icon name="lan" />NS-серверы</div>
          {d.dns.ns.map((n: string, i: number) => <IRow key={i} value={<Mono>{n}</Mono>} />)}
        </div>}
      </>)}

      {tab === 'email' && (!d.email ? <NoData label="Почтовые записи не найдены" icon="mail" /> : <>
        <div className="tg-card">
          <div className="tg-card-title"><Icon name="alternate_email" />Почтовый провайдер</div>
          <IRow icon="mail" label="MX" value={d.email.mx ? <Mono>{d.email.mx}</Mono> : <span style={{ color: 'var(--pv-fg-subtle)' }}>нет</span>} />
        </div>
        <div className="tg-card">
          <div className="tg-card-title"><Icon name="shield_lock" />Защита от спуфинга</div>
          <IRow icon="task_alt" label="SPF" value={<Check ok={d.email.spf}>{d.email.spf ? 'настроен' : 'отсутствует'}</Check>} />
          <IRow icon="key" label="DKIM" value={<Check ok={d.email.dkim}>{d.email.dkim ? 'настроен' : 'отсутствует'}</Check>} />
          <IRow icon="policy" label="DMARC" value={<Check ok={!!d.email.dmarc && d.email.dmarc !== 'none'} warn={d.email.dmarc === 'none'}>{d.email.dmarc ? `p=${d.email.dmarc}` : 'отсутствует'}</Check>} />
        </div>
        {(!d.email.dmarc || d.email.dmarc === 'none') && (
          <div className="tg-card" style={{ padding: 14, display: 'flex', gap: 10, alignItems: 'flex-start' }}>
            <Icon name="lightbulb" style={{ color: 'var(--pv-gold)', fontSize: 20 }} />
            <div style={{ fontSize: 13, color: 'var(--pv-fg-body)', lineHeight: 1.45 }}>
              Рекомендуем настроить DMARC с политикой <b>quarantine</b> или <b>reject</b> — это защитит домен от подделки писем.
            </div>
          </div>
        )}
      </>)}

      {tab === 'subs' && <SubsTab d={d} toast={toast} onTracked={reload} />}
    </div>
  </>;
};

const SubsTab: React.FC<any> = ({ d, toast, onTracked }) => {
  const subs: any[] = useMemo(() => d.subdomains || [], [d.subdomains]);
  const [busy, setBusy] = useState<string | null>(null);
  if (subs.length === 0) return <NoData label="Поддомены не найдены" icon="lan" hint="Поиск идёт через CT-логи crt.sh — запустите /subdomains в боте или подождите планового обхода." />;
  const track = (name: string) => {
    setBusy(name);
    addDomain(name)
      .then(() => { toast(name + ' добавлен', 'check_circle'); onTracked(); })
      .catch((e: any) => toast(e?.message || 'Не удалось добавить', 'error'))
      .finally(() => setBusy(null));
  };
  return <>
    <div className="tg-card" style={{ padding: 14, display: 'flex', alignItems: 'center', gap: 12 }}>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 13, color: 'var(--pv-fg-muted)' }}>Найдено через crt.sh</div>
        <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--pv-fg)' }}>{subs.length} {plural(subs.length, 'поддомен', 'поддомена', 'поддоменов')}</div>
      </div>
    </div>
    <div className="tg-card" style={{ marginTop: 12 }}>
      {subs.map((sub: any) => (
        <div key={sub.name} className="tg-irow">
          <Icon name="subdirectory_arrow_right" style={{ fontSize: 18, color: 'var(--pv-fg-subtle)' }} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="pv-mono" style={{ fontSize: 14, color: 'var(--pv-fg)', overflow: 'hidden', textOverflow: 'ellipsis' }}>{sub.unicode || sub.name}</div>
          </div>
          {sub.tracked
            ? <span className="tg-pill" style={{ background: 'rgba(41,180,115,0.12)', color: 'var(--pv-green-2)' }}><Icon name="visibility" style={{ fontSize: 13 }} />слежу</span>
            : <button className="pv-btn pv-btn-sm" disabled={busy === sub.name} onClick={() => track(sub.name)} style={{ height: 26 }}><Icon name="add" />Следить</button>}
        </div>
      ))}
    </div>
  </>;
};
