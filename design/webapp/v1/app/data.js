/* ============================================================
   Whois Watcher — демо-данные портфеля
   Детерминированная генерация (seeded RNG), чтобы данные
   были стабильны между перезагрузками.
   ============================================================ */
(function () {
  // ── seeded RNG ──────────────────────────────────────────
  let _s = 0x9e3779b9;
  function rnd() {
    _s ^= _s << 13; _s ^= _s >>> 17; _s ^= _s << 5;
    return ((_s >>> 0) % 1e6) / 1e6;
  }
  function pick(a) { return a[Math.floor(rnd() * a.length)]; }
  function int(lo, hi) { return lo + Math.floor(rnd() * (hi - lo + 1)); }
  function chance(p) { return rnd() < p; }

  const TODAY = new Date(2026, 4, 26); // 26 мая 2026 — «сегодня»
  function addDays(d, n) { const x = new Date(d); x.setDate(x.getDate() + n); return x; }
  function fmt(d) {
    const dd = String(d.getDate()).padStart(2, '0');
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    return `${dd}.${mm}.${d.getFullYear()}`;
  }

  // ── словари ─────────────────────────────────────────────
  const roots = ['realstroy','akvamarket','technopark','gorklinika','metluk','devhub','shoplux','fastpay',
    'gruzovik','medplus','eduport','greenhouse','citybank','autoservis','restoclub','bookmarket','smarthome',
    'cloudbox','dataline','finprom','logistika','remontnik','sportbaza','turistik','vesna','zarya','orbita',
    'kapital','prima','vektor','horizont','stroydom','elitservice','mirknig','onlinekassa','platforma',
    'rezerv','sibproekt','torgsnab','uralmash','flagman','holding','energosbyt','promtech','dialog','kvartira',
    'lombard','master','novosel','ostров','partner','rocket','servis','traktor','union','vityaz','workspace',
    'yarmarka','zoomarket','aптека','банкир','вектор2','глобус','дом','europa','favorit','garant'];
  const tlds = ['.ru','.рф','.com','.net','.org','.io','.dev','.shop','.online','.store','.tech','.pro'];
  const registrars = [
    { n: 'RU-CENTER', h: 'nic.ru' }, { n: 'REG.RU', h: 'reg.ru' }, { n: 'Timeweb', h: 'timeweb.ru' },
    { n: 'Beget', h: 'beget.com' }, { n: 'R01', h: 'r01.ru' }, { n: 'Domenus', h: 'domenus.ru' },
    { n: 'GoDaddy', h: 'godaddy.com' }, { n: 'Namecheap', h: 'namecheap.com' }, { n: 'Cloudflare', h: 'cloudflare.com' },
  ];
  const nsProviders = [
    { p: 'nic.ru', ns: ['ns1.nic.ru','ns2.nic.ru','ns3.nic.ru'] },
    { p: 'Cloudflare', ns: ['kira.ns.cloudflare.com','rob.ns.cloudflare.com'] },
    { p: 'reg.ru', ns: ['ns1.reg.ru','ns2.reg.ru'] },
    { p: 'Timeweb', ns: ['ns1.timeweb.ru','ns2.timeweb.org'] },
    { p: 'Beget', ns: ['ns1.beget.com','ns2.beget.com','ns1.beget.pro'] },
    { p: 'Yandex Cloud', ns: ['ns1.yandexcloud.net','ns2.yandexcloud.net'] },
    { p: 'Selectel', ns: ['ns1.selectel.org','ns2.selectel.ru'] },
  ];
  const sslIssuers = ['Let\u2019s Encrypt','GlobalSign','Sectigo','DigiCert','Google Trust Services','ZeroSSL'];
  const mxProviders = ['Yandex 360','Google Workspace','Mail.ru для бизнеса','Self-hosted (Postfix)','Beget Mail','Zoho Mail'];
  const asns = [
    { a: 'AS13238', o: 'Yandex.Cloud' }, { a: 'AS200000', o: 'Hosting Timeweb' },
    { a: 'AS197695', o: 'Reg.ru Hosting' }, { a: 'AS13335', o: 'Cloudflare' },
    { a: 'AS49505', o: 'Selectel' }, { a: 'AS48282', o: 'Beget Hosting' },
    { a: 'AS16509', o: 'Amazon AWS' },
  ];
  const groups = [
    { id: 'g_realstroy', name: 'Реалстрой', kind: 'client', color: 'a1', icon: 'apartment' },
    { id: 'g_akva',      name: 'АкваМаркет', kind: 'client', color: 'a7', icon: 'storefront' },
    { id: 'g_techno',    name: 'ТехноПарк', kind: 'client', color: 'a0', icon: 'memory' },
    { id: 'g_klinika',   name: 'Городская клиника', kind: 'client', color: 'a2', icon: 'local_hospital' },
    { id: 'g_personal',  name: 'Мои проекты', kind: 'personal', color: 'a3', icon: 'person' },
    { id: 'g_parking',   name: 'Парковка доменов', kind: 'personal', color: 'a6', icon: 'inventory_2' },
  ];
  const statusFlags = ['clientTransferProhibited','clientUpdateProhibited','clientDeleteProhibited',
    'serverTransferProhibited','clientHold','pendingDelete','redemptionPeriod','autoRenewPeriod','ok'];

  // ── генерация доменов ───────────────────────────────────
  const usedNames = new Set();
  const domains = [];
  const N = 300;
  let i = 0;
  while (domains.length < N) {
    i++;
    let root = pick(roots);
    // префиксы/поддоменные клиентские варианты для разнообразия
    if (chance(0.18)) root = pick(['app','api','shop','my','lk','cdn','mail','dev','stage','blog']) + '-' + root;
    const tld = pick(tlds);
    const name = (root + tld).toLowerCase();
    if (usedNames.has(name)) continue;
    usedNames.add(name);

    const noData = chance(0.025);
    const isWishlist = chance(0.05);

    // распределение сроков: немного критичных, побольше «здоровых»
    let daysLeft;
    const roll = rnd();
    if (roll < 0.05) daysLeft = int(-25, -1);       // истёк
    else if (roll < 0.13) daysLeft = int(0, 6);     // < 7 дней
    else if (roll < 0.30) daysLeft = int(7, 29);    // 7–30
    else if (roll < 0.55) daysLeft = int(30, 89);   // 30–90
    else daysLeft = int(90, 1400);                  // здоровые

    const expires = addDays(TODAY, daysLeft);
    const regYearsAgo = int(1, 14);
    const registered = addDays(TODAY, -(regYearsAgo * 365 + int(0, 300)));
    const updated = addDays(TODAY, -int(5, 220));
    const reg = pick(registrars);
    const nsp = pick(nsProviders);

    // статусы
    let flags = [];
    if (daysLeft < 0 && chance(0.5)) flags = chance(0.5) ? ['redemptionPeriod'] : ['pendingDelete'];
    else if (chance(0.04)) flags = ['clientHold'];
    else flags = ['clientTransferProhibited', 'clientUpdateProhibited'].slice(0, int(1, 2));

    // SSL
    const hasSSL = !noData && !isWishlist && chance(0.9);
    const sslDays = hasSSL ? int(-5, 320) : null;
    const ssl = hasSSL ? {
      issuer: pick(sslIssuers),
      validTo: fmt(addDays(TODAY, sslDays)),
      daysLeft: sslDays,
      grade: sslDays < 0 ? 'expired' : pick(['A+','A','A','A','B']),
      tls: pick(['TLS 1.3','TLS 1.3','TLS 1.2']),
    } : null;

    // DNS
    const asn = pick(asns);
    const dns = noData ? null : {
      a: [`${int(5,217)}.${int(0,255)}.${int(0,255)}.${int(1,254)}`],
      aaaa: chance(0.4) ? [`2a02:6b8:${int(0,9999).toString(16)}::${int(1,99)}`] : [],
      ns: nsp.ns,
      provider: nsp.p,
      asn: asn.a, asnOrg: asn.o,
      dnssec: chance(0.35),
    };

    // Email
    const mx = pick(mxProviders);
    const dmarcPolicy = pick(['none','none','quarantine','reject', null]);
    const email = noData ? null : {
      mx, hasMX: true,
      spf: chance(0.85),
      dkim: chance(0.65),
      dmarc: dmarcPolicy,
    };

    // поддомены
    const subCount = noData ? 0 : int(0, 48);

    // assign groups (0–2)
    const gset = [];
    if (isWishlist) gset.push('g_parking');
    else {
      if (chance(0.7)) gset.push(pick(['g_realstroy','g_akva','g_techno','g_klinika','g_personal']));
      if (chance(0.15)) { const g2 = pick(groups).id; if (!gset.includes(g2)) gset.push(g2); }
    }

    // health score 0..100
    let health = 100;
    if (noData) health = 0;
    else {
      if (daysLeft < 0) health -= 60; else if (daysLeft < 7) health -= 38; else if (daysLeft < 30) health -= 20; else if (daysLeft < 90) health -= 6;
      if (ssl) { if (ssl.daysLeft < 0) health -= 22; else if (ssl.daysLeft < 14) health -= 12; } else health -= 10;
      if (!email || !email.spf) health -= 6;
      if (!email || !email.dmarc) health -= 8; else if (email.dmarc === 'none') health -= 4;
      if (dns && !dns.dnssec) health -= 4;
      if (flags.includes('clientHold') || flags.includes('pendingDelete') || flags.includes('redemptionPeriod')) health -= 30;
      health = Math.max(0, Math.min(100, health + int(-3, 3)));
    }

    // notifications
    const notifyExpiry = !isWishlist && chance(0.86);
    const notifyNS = chance(0.4), notifyReg = chance(0.7), notifyStatus = chance(0.65);

    // renewal cost (₽/год)
    const tldCost = { '.ru': 199, '.рф': 199, '.com': 1090, '.net': 1290, '.org': 1190, '.io': 3690,
      '.dev': 1490, '.shop': 2390, '.online': 2190, '.store': 3290, '.tech': 2890, '.pro': 1690 };
    const cost = tldCost[tld] || 990;

    domains.push({
      id: 'd' + domains.length,
      name,
      unicode: name,
      noData, isWishlist,
      registered: fmt(registered),
      expires: noData ? null : fmt(expires),
      updated: fmt(updated),
      daysLeft: noData ? null : daysLeft,
      registrar: reg.n, registrarHost: reg.h,
      flags,
      ssl, dns, email,
      subCount,
      groups: gset,
      health,
      notify: { expiry: notifyExpiry, ns: notifyNS, registrar: notifyReg, status: notifyStatus },
      cost,
      addedAt: fmt(addDays(TODAY, -int(2, 700))),
      lastCheck: pick(['только что','5 мин назад','1 ч назад','3 ч назад','сегодня, 09:00','вчера']),
    });
  }

  // ── лента алертов / изменений ───────────────────────────
  const alertTypes = [
    { t: 'expiry', icon: 'hourglass_bottom', sev: 'danger', verb: (d, x) => `истекает через ${x} дн.` },
    { t: 'expiry_soon', icon: 'schedule', sev: 'warn', verb: (d, x) => `напоминание: ${x} дней до истечения` },
    { t: 'ssl', icon: 'lock_clock', sev: 'warn', verb: (d, x) => `SSL-сертификат истекает через ${x} дн.` },
    { t: 'ns', icon: 'dns', sev: 'info', verb: (d, x) => `сменились NS-серверы` },
    { t: 'registrar', icon: 'sync_alt', sev: 'info', verb: (d, x) => `сменился регистратор` },
    { t: 'status', icon: 'gpp_maybe', sev: 'danger', verb: (d, x) => `новый статус: clientHold` },
    { t: 'subdomain', icon: 'lan', sev: 'info', verb: (d, x) => `обнаружено ${x} новых поддоменов` },
    { t: 'dmarc', icon: 'mark_email_unread', sev: 'warn', verb: (d, x) => `DMARC-политика отсутствует` },
    { t: 'freed', icon: 'celebration', sev: 'success', verb: (d, x) => `домен освободился — можно регистрировать` },
    { t: 'expired', icon: 'error', sev: 'danger', verb: (d, x) => `регистрация истекла` },
  ];
  const when = ['только что','12 мин назад','40 мин назад','1 ч назад','2 ч назад','сегодня, 09:00',
    'вчера, 18:42','вчера, 09:00','2 дня назад','3 дня назад','5 дней назад','неделю назад'];
  const alerts = [];
  for (let k = 0; k < 60; k++) {
    const dom = pick(domains);
    const at = pick(alertTypes);
    const x = at.t === 'subdomain' ? int(1, 6) : (dom.daysLeft != null ? Math.max(1, dom.daysLeft) : int(1, 30));
    alerts.push({
      id: 'a' + k,
      domain: dom.name,
      domainId: dom.id,
      type: at.t,
      icon: at.icon,
      sev: at.sev,
      text: at.verb(dom, x),
      when: pick(when),
      unread: k < 8,
      group: dom.groups[0] || null,
    });
  }

  // ── история изменений для карточки домена (пример) ───────
  function historyFor(d) {
    return [
      { icon: 'fact_check', text: 'Плановая проверка WHOIS — без изменений', when: d.lastCheck, sev: 'neutral' },
      { icon: 'lock', text: `SSL обновлён — ${d.ssl ? d.ssl.issuer : 'нет данных'}`, when: '6 дней назад', sev: 'success' },
      { icon: 'dns', text: `NS-серверы: ${d.dns ? d.dns.provider : '—'}`, when: '3 недели назад', sev: 'info' },
      { icon: 'event_available', text: `Срок продлён до ${d.expires || '—'}`, when: '2 месяца назад', sev: 'success' },
      { icon: 'add_circle', text: 'Добавлен на слежение', when: d.addedAt, sev: 'neutral' },
    ];
  }

  // ── пользователь / настройки ────────────────────────────
  const user = {
    name: 'Никита М.',
    handle: '@nmetluk',
    timezone: 'Europe/Moscow',
    notifyHour: 9,
    notifyDays: [30, 7, 1],
    lang: 'Русский',
    plan: 'Бесплатный',
    limit: 50000,
  };

  window.DATA = { domains, groups, alerts, user, statusFlags, historyFor, TODAY, fmt, addDays };
})();
