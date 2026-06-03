/* ============================================================
   Core helpers + shared primitives  → window
   ============================================================ */
const { useState, useEffect, useRef, useMemo, useCallback } = React;

const Icon = ({ name, style, className, onClick }) => (
  <span className={"material-symbols-rounded" + (className ? " " + className : "")} style={style} onClick={onClick}>{name}</span>
);

// ── status of a domain by days left ─────────────────────────
function statusOf(d) {
  if (d.isWishlist) return { key: 'wish', label: 'Wishlist', color: 'wish', dot: 'var(--pv-violet)' };
  if (d.noData || d.daysLeft == null) return { key: 'gray', label: 'Нет данных', color: 'gray', dot: 'var(--pv-fg-subtle)' };
  if (d.daysLeft < 0) return { key: 'red', label: 'Истёк', color: 'red', dot: 'var(--pv-red)' };
  if (d.daysLeft < 7) return { key: 'red', label: 'Критично', color: 'red', dot: 'var(--pv-red)' };
  if (d.daysLeft < 30) return { key: 'gold', label: 'Скоро', color: 'gold', dot: 'var(--pv-gold)' };
  return { key: 'green', label: 'В норме', color: 'green', dot: 'var(--pv-green)' };
}
function daysText(d) {
  if (d.isWishlist) return 'жду освобождения';
  if (d.daysLeft == null) return 'нет данных';
  if (d.daysLeft < 0) return `истёк ${-d.daysLeft} дн. назад`;
  if (d.daysLeft === 0) return 'истекает сегодня';
  return `через ${d.daysLeft} ${plural(d.daysLeft, 'день','дня','дней')}`;
}
function plural(n, one, few, many) {
  const m10 = n % 10, m100 = n % 100;
  if (m10 === 1 && m100 !== 11) return one;
  if (m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20)) return few;
  return many;
}
function puckText(d) {
  if (d.isWishlist) return <Icon name="target" style={{ fontSize: 18 }} />;
  if (d.daysLeft == null) return '—';
  if (d.daysLeft < 0) return <Icon name="error" style={{ fontSize: 18 }} />;
  return <span>{d.daysLeft}<small>дн</small></span>;
}
function groupById(id) { return (window.DATA.groups || []).find(g => g.id === id); }
function avatarHue(color) {
  const map = { a0:'#9c4bb5', a1:'#3498db', a2:'#27ae60', a3:'#e67e22', a4:'#e74c3c', a5:'#8e44ad', a6:'#f39c12', a7:'#16a085' };
  return map[color] || '#9aa1a8';
}

// ── Health ring ─────────────────────────────────────────────
const Ring = ({ value, size = 56, stroke = 6, showLabel = true, label }) => {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const off = c * (1 - value / 100);
  const col = value >= 75 ? 'var(--pv-green)' : value >= 45 ? 'var(--pv-gold)' : 'var(--pv-red)';
  return (
    <div className="tg-ring" style={{ width: size, height: size }}>
      <svg width={size} height={size}>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="var(--pv-muted)" strokeWidth={stroke} />
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={col} strokeWidth={stroke}
          strokeLinecap="round" strokeDasharray={c} strokeDashoffset={off}
          style={{ transition: 'stroke-dashoffset 0.6s ease' }} />
      </svg>
      {showLabel && (
        <div className="tg-ring-val" style={{ fontSize: size * 0.3 }}>
          {value}{label && <span style={{ fontSize: size * 0.13, color: 'var(--pv-fg-muted)', fontWeight: 700, letterSpacing: '0.04em' }}>{label}</span>}
        </div>
      )}
    </div>
  );
};

// ── small badge for ssl/dns/email checks ────────────────────
const Check = ({ ok, warn, children }) => (
  <span className="tg-pill" style={{
    background: warn ? 'rgba(244,185,33,0.16)' : ok ? 'rgba(41,180,115,0.12)' : 'rgba(230,64,58,0.12)',
    color: warn ? '#b07d00' : ok ? 'var(--pv-green-2)' : 'var(--pv-red)',
  }}>
    <Icon name={warn ? 'warning' : ok ? 'check_circle' : 'cancel'} style={{ fontSize: 13 }} />{children}
  </span>
);

// ── group chip used inside rows / cards ─────────────────────
const GroupTag = ({ id, sm }) => {
  const g = groupById(id); if (!g) return null;
  return (
    <span className="tg-mini-tag" style={{ background: avatarHue(g.color) + '22', color: avatarHue(g.color), display: 'inline-flex', alignItems: 'center', gap: 3 }}>
      {!sm && <Icon name={g.icon} style={{ fontSize: 11 }} />}{g.name}
    </span>
  );
};

// row in detail cards
const IRow = ({ icon, label, value, mono, tap, onClick, chev, children }) => (
  <div className={"tg-irow" + (tap ? " tap" : "") + (children ? " col" : "")} onClick={onClick}>
    {icon && <div className="tg-ir-ico"><Icon name={icon} /></div>}
    {label && <div className="tg-ir-label">{label}</div>}
    {value != null && <div className={"tg-ir-val" + (mono ? " mono" : "")}>{value}{chev && <Icon name="chevron_right" className="tg-ir-chev" style={{ fontSize: 20 }} />}</div>}
    {children}
  </div>
);

Object.assign(window, { Icon, Ring, Check, GroupTag, IRow, statusOf, daysText, plural, puckText, groupById, avatarHue });
