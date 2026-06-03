/* ============================================================
   Ещё: группы, wishlist, статистика, импорт/экспорт, настройки,
   добавление домена.
   ============================================================ */
function MoreScreen({ domains, user, go, toast, theme, setTheme }) {
  const counts = {
    wish: domains.filter(d => d.isWishlist).length,
    total: domains.length,
  };
  return (
    <div className="tg-pad-b">
      {/* user header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '18px 16px', background: 'var(--pv-panel)', borderBottom: '1px solid var(--pv-border)' }}>
        <div className="pv-avatar a1 lg" style={{ width: 52, height: 52, fontSize: 18 }}>НМ</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 17, fontWeight: 700, color: 'var(--pv-fg)' }}>{user.name}</div>
          <div style={{ fontSize: 13, color: 'var(--pv-fg-muted)' }}>{user.handle} · {counts.total} {plural(counts.total, 'домен','домена','доменов')}</div>
        </div>
        <span className="tg-pill" style={{ background: 'var(--pv-muted)', color: 'var(--pv-fg-muted)' }}>{user.plan}</span>
      </div>

      <div className="tg-section-label">Организация</div>
      <div className="tg-card" style={{ margin: '0 12px', borderRadius: 12 }}>
        <MoreRow icon="folder_special" color="a1" label="Группы и теги" sub="Клиенты, проекты, парковка" onClick={() => go({ screen: 'groups' })} chev />
        <MoreRow icon="target" color="a5" label="Wishlist" sub="Жду освобождения доменов" val={counts.wish} onClick={() => go({ screen: 'wishlist' })} chev />
        <MoreRow icon="insights" color="a2" label="Статистика" sub="Сводка по портфелю" onClick={() => go({ screen: 'stats' })} chev />
      </div>

      <div className="tg-section-label">Данные</div>
      <div className="tg-card" style={{ margin: '0 12px', borderRadius: 12 }}>
        <MoreRow icon="upload_file" color="a3" label="Импорт доменов" sub="TXT или CSV, до 50 000" onClick={() => go({ screen: 'import' })} chev />
        <MoreRow icon="download" color="a7" label="Экспорт в CSV" sub="Весь список с данными" onClick={() => toast('Файл domains.csv готов', 'download')} chev />
      </div>

      <div className="tg-section-label">Приложение</div>
      <div className="tg-card" style={{ margin: '0 12px', borderRadius: 12 }}>
        <MoreRow icon="settings" color="a0" label="Настройки" sub="Часовой пояс, напоминания, язык" onClick={() => go({ screen: 'settings' })} chev />
        <div className="tg-irow" style={{ minHeight: 56 }}>
          <div className="tg-grp-ico" style={{ width: 34, height: 34, background: 'var(--pv-fg)' }}><Icon name="dark_mode" style={{ fontSize: 18 }} /></div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--pv-fg)' }}>Тёмная тема</div>
            <div style={{ fontSize: 12, color: 'var(--pv-fg-muted)' }}>Следует теме Telegram</div>
          </div>
          <div className={"pv-toggle" + (theme === 'dark' ? " on" : "")} onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} />
        </div>
      </div>

      <div style={{ textAlign: 'center', padding: '24px 16px', color: 'var(--pv-fg-subtle)', fontSize: 12 }}>
        Whois Watcher · v0.4.0<br />Бесплатный сервис · GitHub
      </div>
    </div>
  );
}

const MoreRow = ({ icon, color, label, sub, val, onClick, chev }) => (
  <div className="tg-grp" onClick={onClick} style={{ borderBottom: '1px solid var(--pv-divider)' }}>
    <div className="tg-grp-ico" style={{ width: 38, height: 38, background: avatarHue(color) }}><Icon name={icon} /></div>
    <div className="tg-grp-main">
      <div className="tg-grp-name">{label}</div>
      {sub && <div className="tg-grp-sub">{sub}</div>}
    </div>
    {val != null && <span className="tg-grp-n">{val}</span>}
    {chev && <Icon name="chevron_right" style={{ color: 'var(--pv-fg-subtle)' }} />}
  </div>
);

// ── Groups ──────────────────────────────────────────────────
function GroupsScreen({ domains, go, toast }) {
  const groups = window.DATA.groups;
  const clients = groups.filter(g => g.kind === 'client');
  const personal = groups.filter(g => g.kind === 'personal');
  const countFor = id => domains.filter(d => d.groups.includes(id)).length;
  const renderGroup = g => (
    <div key={g.id} className="tg-grp" onClick={() => go({ tab: 'list', groupFilter: g.id })}>
      <div className="tg-grp-ico" style={{ background: avatarHue(g.color) }}><Icon name={g.icon} /></div>
      <div className="tg-grp-main">
        <div className="tg-grp-name">{g.name}</div>
        <div className="tg-grp-sub">{countFor(g.id)} {plural(countFor(g.id),'домен','домена','доменов')} · {domains.filter(d => d.groups.includes(g.id)).reduce((s,d)=>s+d.cost,0).toLocaleString('ru-RU')} ₽/год</div>
      </div>
      <Icon name="chevron_right" style={{ color: 'var(--pv-fg-subtle)' }} />
    </div>
  );
  return (
    <div className="tg-pad-b">
      <div className="tg-hint" style={{ padding: '14px 16px 4px' }}>Группируйте домены по клиентам и проектам — фильтр, бюджет и массовые действия работают по группам.</div>
      <div className="tg-section-label">Клиенты</div>
      <div className="tg-card" style={{ margin: '0 12px', borderRadius: 12 }}>{clients.map(renderGroup)}</div>
      <div className="tg-section-label">Личное</div>
      <div className="tg-card" style={{ margin: '0 12px', borderRadius: 12 }}>{personal.map(renderGroup)}</div>
      <div style={{ padding: 14 }}>
        <button className="pv-btn" style={{ width: '100%', justifyContent: 'center' }} onClick={() => toast('Создание группы', 'create_new_folder')}><Icon name="add" />Новая группа</button>
      </div>
    </div>
  );
}

// ── Wishlist ────────────────────────────────────────────────
function WishlistScreen({ domains, onOpen, go }) {
  const wish = domains.filter(d => d.isWishlist);
  return (
    <div className="tg-pad-b">
      <div className="tg-card" style={{ margin: 14, padding: 16, display: 'flex', gap: 12, alignItems: 'flex-start' }}>
        <Icon name="target" style={{ fontSize: 28, color: 'var(--pv-violet)' }} />
        <div style={{ fontSize: 13, color: 'var(--pv-fg-body)', lineHeight: 1.45 }}>
          Добавьте занятый домен — бот пришлёт <b>одно уведомление</b>, как только он освободится. Подходит, чтобы поймать момент регистрации.
        </div>
      </div>
      {wish.length === 0
        ? <div className="tg-empty2"><Icon name="target" /><b>Wishlist пуст</b><div>Добавьте домен, который хотите занять</div></div>
        : <div className="tg-card" style={{ margin: '0 12px', borderRadius: 12 }}>
            {wish.map(d => (
              <div key={d.id} className="tg-irow tap" onClick={() => onOpen(d)}>
                <div className="tg-puck wish" style={{ width: 36, height: 36 }}><Icon name="target" style={{ fontSize: 18 }} /></div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--pv-fg)' }}>{d.name}</div>
                  <div style={{ fontSize: 12, color: 'var(--pv-fg-muted)' }}>занят · проверяю ежедневно</div>
                </div>
                <span className="tg-pill" style={{ background: 'rgba(142,68,173,0.12)', color: 'var(--pv-violet)' }}>жду</span>
              </div>
            ))}
          </div>}
    </div>
  );
}

// ── Stats ───────────────────────────────────────────────────
function StatsScreen({ domains }) {
  const s = useMemo(() => {
    const r = { total: domains.length, data: 0, nodata: 0, d7: 0, d30: 0, d90: 0, silent: 0, wish: 0, subs: 0 };
    domains.forEach(d => {
      if (d.isWishlist) r.wish++;
      if (d.noData || d.daysLeft == null) r.nodata++; else r.data++;
      if (d.daysLeft != null && d.daysLeft >= 0) { if (d.daysLeft < 7) r.d7++; if (d.daysLeft < 30) r.d30++; if (d.daysLeft < 90) r.d90++; }
      if (!d.notify.expiry && !d.isWishlist) r.silent++;
      r.subs += d.subCount;
    });
    return r;
  }, [domains]);
  return (
    <div className="tg-pad tg-pad-b">
      <div className="tg-card">
        <div className="tg-card-title"><Icon name="language" />Всего доменов</div>
        <IRow icon="check_circle" label="С данными" value={s.data} />
        <IRow icon="hourglass_empty" label="Без данных" value={s.nodata} />
        <IRow icon="target" label="В wishlist" value={s.wish} />
        <IRow icon="lan" label="Поддоменов отслеживается" value={s.subs} />
      </div>
      <div className="tg-card">
        <div className="tg-card-title"><Icon name="schedule" />Истекает</div>
        <IRow icon="priority_high" label="За 7 дней" value={<span style={{ color: s.d7 ? 'var(--pv-red)' : undefined }}>{s.d7}</span>} />
        <IRow icon="hourglass_bottom" label="За 30 дней" value={<span style={{ color: s.d30 ? 'var(--pv-gold)' : undefined }}>{s.d30}</span>} />
        <IRow icon="calendar_month" label="За 90 дней" value={s.d90} />
      </div>
      <div className="tg-card">
        <div className="tg-card-title"><Icon name="tune" />Прочее</div>
        <IRow icon="notifications_off" label="Без уведомлений" value={s.silent} />
        <IRow icon="trending_up" label="Добавлено за месяц" value={12} />
      </div>
    </div>
  );
}

// ── Settings ────────────────────────────────────────────────
function SettingsScreen({ user, toast }) {
  const [hour, setHour] = useState(user.notifyHour);
  const [days, setDays] = useState('30, 7, 1');
  return (
    <div className="tg-pad-b">
      <div className="tg-section-label">Напоминания</div>
      <div className="tg-card" style={{ margin: '0 12px', borderRadius: 12 }}>
        <IRow icon="schedule" label="Время напоминаний" value={<span>{String(hour).padStart(2,'0')}:00</span>} tap chev onClick={() => { const h = (hour + 1) % 24; setHour(h); }} />
        <div className="tg-irow col">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, width: '100%' }}>
            <Icon name="event_repeat" style={{ color: 'var(--pv-fg-muted)' }} />
            <span style={{ fontSize: 14, color: 'var(--pv-fg)', fontWeight: 700, flex: 1 }}>Дни напоминаний</span>
          </div>
          <div className="tg-seg" style={{ width: '100%' }}>
            {['1','30, 7, 1','60, 30, 14, 7, 3, 1'].map((p, i) => (
              <button key={i} className={days === p ? 'active' : ''} onClick={() => setDays(p)} style={{ fontSize: 12 }}>
                {['За день','Стандарт','Часто'][i]}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="tg-section-label">Регион</div>
      <div className="tg-card" style={{ margin: '0 12px', borderRadius: 12 }}>
        <IRow icon="public" label="Часовой пояс" value="Europe/Moscow" tap chev onClick={() => toast('Выбор часового пояса', 'public')} />
        <IRow icon="translate" label="Язык" value="Русский" tap chev onClick={() => toast('Выбор языка', 'translate')} />
      </div>

      <div className="tg-section-label">Лимит</div>
      <div className="tg-card" style={{ margin: '0 12px', borderRadius: 12, padding: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
          <span style={{ fontSize: 13, color: 'var(--pv-fg-muted)' }}>Использовано</span>
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--pv-fg)' }}>300 / 50 000</span>
        </div>
        <div className="tg-distbar"><i style={{ width: '0.6%', background: 'var(--pv-green)' }} /></div>
      </div>

      <div className="tg-section-label" style={{ color: 'var(--pv-red)' }}>Опасная зона</div>
      <div className="tg-card" style={{ margin: '0 12px', borderRadius: 12 }}>
        <div className="tg-menu-row danger" onClick={() => toast('Подтвердите удаление данных', 'warning')} style={{ padding: '14px 16px' }}>
          <Icon name="delete_forever" />Удалить все мои данные
        </div>
      </div>
    </div>
  );
}

// ── Add domain ──────────────────────────────────────────────
function AddScreen({ value, setValue, group, setGroup }) {
  const groups = window.DATA.groups;
  const valid = /^[a-zа-я0-9-]+\.[a-zа-я0-9.-]+$/i.test(value.trim());
  return (
    <div className="tg-pad tg-pad-b">
      <div className="tg-card" style={{ padding: 16 }}>
        <div className="pv-field">
          <label className="pv-field-label">Домен</label>
          <div className={"tg-search" + (value ? " focus" : "")} style={{ height: 44 }}>
            <Icon name="language" />
            <input autoFocus value={value} placeholder="example.com" onChange={e => setValue(e.target.value)} style={{ fontSize: 16 }} />
            {value && valid && <Icon name="check_circle" style={{ color: 'var(--pv-green)' }} />}
          </div>
          <div className="pv-field-help">Можно вставить ссылку — host извлечётся автоматически. IDN → punycode.</div>
        </div>
      </div>

      <div className="tg-card" style={{ marginTop: 12 }}>
        <div className="tg-card-title"><Icon name="folder" />Добавить в группу</div>
        <div className="tg-chips" style={{ padding: '4px 14px 14px', margin: 0 }}>
          <button className={"tg-chip2" + (!group ? " active" : "")} onClick={() => setGroup(null)}>Без группы</button>
          {groups.map(g => (
            <button key={g.id} className={"tg-chip2" + (group === g.id ? " active" : "")} onClick={() => setGroup(g.id)}>
              <Icon name={g.icon} />{g.name}
            </button>
          ))}
        </div>
      </div>

      <div className="tg-card" style={{ marginTop: 12 }}>
        <div className="tg-card-title"><Icon name="notifications" />Уведомления по умолчанию</div>
        <IRow icon="event_busy" label="Истечение регистрации" value={<span style={{ color: 'var(--pv-green-2)' }}>вкл · 30, 7, 1</span>} />
        <IRow icon="sync_alt" label="Смена регистратора" value={<span style={{ color: 'var(--pv-green-2)' }}>вкл</span>} />
        <IRow icon="gpp_maybe" label="Изменение статусов" value={<span style={{ color: 'var(--pv-green-2)' }}>вкл</span>} />
      </div>
      <div className="tg-hint">После добавления бот сразу подгрузит WHOIS, SSL, DNS и email-записи.</div>
    </div>
  );
}

// ── Import ──────────────────────────────────────────────────
function ImportScreen({ toast }) {
  const [stage, setStage] = useState('drop');
  return (
    <div className="tg-pad tg-pad-b">
      {stage === 'drop' && (
        <>
          <div onClick={() => setStage('preview')} style={{ border: '2px dashed var(--pv-border-2)', borderRadius: 14, padding: '40px 20px', textAlign: 'center', cursor: 'pointer', background: 'var(--pv-panel)' }}>
            <Icon name="upload_file" style={{ fontSize: 44, color: 'var(--pv-cta)' }} />
            <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--pv-fg)', marginTop: 10 }}>Выберите файл</div>
            <div style={{ fontSize: 13, color: 'var(--pv-fg-muted)', marginTop: 4 }}>TXT или CSV · по одному домену на строку</div>
          </div>
          <div className="tg-hint" style={{ padding: '14px 4px' }}>Лимит: 50 000 доменов за раз, файл до 5 МБ. Дубли и невалидные строки отсеются автоматически.</div>
        </>
      )}
      {stage === 'preview' && (
        <>
          <div className="tg-card" style={{ padding: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
              <Icon name="description" style={{ fontSize: 26, color: 'var(--pv-cta)' }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--pv-fg)' }}>domains_realstroy.csv</div>
                <div style={{ fontSize: 12, color: 'var(--pv-fg-muted)' }}>248 строк · 14 КБ</div>
              </div>
            </div>
            <div className="tg-legend">
              <div className="tg-legend-row"><Icon name="check_circle" style={{ color: 'var(--pv-green)', fontSize: 18 }} /><span>Валидных и новых</span><span className="tg-lg-n">214</span></div>
              <div className="tg-legend-row"><Icon name="visibility" style={{ color: 'var(--pv-fg-muted)', fontSize: 18 }} /><span>Уже отслеживается</span><span className="tg-lg-n">28</span></div>
              <div className="tg-legend-row"><Icon name="cancel" style={{ color: 'var(--pv-red)', fontSize: 18 }} /><span>Невалидных</span><span className="tg-lg-n">6</span></div>
            </div>
          </div>
          <div className="tg-card" style={{ marginTop: 12 }}>
            <div className="tg-card-title"><Icon name="preview" />Примеры</div>
            {['realstroy.ru','shop-akvamarket.com','lk.technopark.io','clinic-spb.ru','parking.metluk.dev'].map(n => (
              <IRow key={n} icon="language" value={<span className="pv-mono" style={{ fontWeight: 400, fontSize: 13 }}>{n}</span>} />
            ))}
            <div className="tg-irow" style={{ color: 'var(--pv-fg-subtle)', fontSize: 13 }}>… и ещё 209</div>
          </div>
        </>
      )}
    </div>
  );
}

Object.assign(window, { MoreScreen, GroupsScreen, WishlistScreen, StatsScreen, SettingsScreen, AddScreen, ImportScreen });
