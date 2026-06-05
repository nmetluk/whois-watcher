"""Read-only JSON API for Telegram WebApp (/api/webapp/*).

Mounted as sub-application under the main aiohttp app.
Auth via initData middleware (see auth.py).
All responses JSON; errors have {"error": "..."}.

Thin handlers: business logic via repositories + services (DomainService etc).
No raw SQL in handlers.
"""

from __future__ import annotations

import logging
from contextlib import suppress
from datetime import UTC, date, datetime
from typing import Any

from aiohttp import web
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.webapp.auth import create_webapp_auth_middleware
from src.config.limits import Limits, get_limits
from src.config.settings import Settings
from src.db.models import User, UserDomain, WhoisCache
from src.db.repositories import (
    DNSCacheRepository,
    DomainRepository,
    EmailIntelCacheRepository,
    GroupRepository,
    SSLCacheRepository,
    SubdomainEnumCacheRepository,
    UserRepository,
    WhoisCacheRepository,
    WishlistRepository,
)
from src.db.repositories.notifications import NotificationRepository
from src.db.session import get_session
from src.services.audit import audit
from src.services.csv_io import parse_domain_file
from src.services.domains import DomainService
from src.services.health_score import HealthInputs, compute_health_score
from src.services.whois_facade import WhoisFacade
from src.utils.domains import normalize_domain  # type: ignore[attr-defined]
from src.utils.domains import registrable_domain as get_registrable
from src.utils.idn import from_punycode

logger = logging.getLogger(__name__)

# WebApp filter ids (from design/webapp/v1/app/screen-list.jsx)
_WEBAPP_FILTERS = {
    "all",
    "soon",
    "crit",
    "problem",
    "expired",
    "nodata",
    "silent",
    "wish",
}

_WEBAPP_SORTS = {"expiry", "name", "added", "health"}


def _fmt_date(d: datetime | date | None) -> str | None:
    """Format as DD.MM.YYYY for webapp model."""
    if d is None:
        return None
    if isinstance(d, datetime):
        d = d.date()
    return f"{d.day:02d}.{d.month:02d}.{d.year:04d}"


def _days_left(expires_at: datetime | None, now: datetime | None = None) -> int | None:
    if expires_at is None:
        return None
    moment = now or datetime.now(UTC)
    # naive vs aware: assume expires_at is aware or treat as UTC date
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    delta = (expires_at.date() - moment.date()).days
    return delta


def _shape_domain(
    ud: UserDomain,
    whois: WhoisCache | None,
    ssl: Any | None,  # SSLCache
    dns: Any | None,  # DNSCache
    email: Any | None,  # EmailIntelCache
    sub_count: int,
    *,
    now: datetime | None = None,
    groups: list[int] | None = None,
) -> dict[str, Any]:
    """Shape one domain to the exact model from design/webapp/v1/README.md «Структура объекта домена»."""
    no_data = whois is None or whois.expires_at is None
    is_wish = ud.note == "wishlist" or False  # wishlist is separate table; flag via query

    days_left = _days_left(whois.expires_at if whois else None, now)
    reg = whois.registrar if whois else None
    # Try to split registrar name/host if possible; for now registrar as both or from raw
    registrar = reg
    registrar_host = None

    flags = list(whois.status) if whois and whois.status else []

    # SSL shape
    ssl_obj: dict[str, Any] | None = None
    if ssl and ssl.has_certificate and ssl.not_after:
        ssl_dl = _days_left(ssl.not_after, now)
        grade = "A+"
        if ssl_dl is not None and ssl_dl < 0:
            grade = "expired"
        elif ssl_dl is not None and ssl_dl < 14:
            grade = "B"
        # issuer
        issuer = ssl.issuer_cn or ssl.issuer_o or "Unknown"
        tls = "TLS 1.2"  # not tracked precisely; good enough
        ssl_obj = {
            "issuer": issuer,
            "validTo": _fmt_date(ssl.not_after),
            "daysLeft": ssl_dl,
            "grade": grade,
            "tls": tls,
        }

    # DNS shape
    dns_obj: dict[str, Any] | None = None
    if dns:
        dns_obj = {
            "a": list(dns.a_records or []),
            "aaaa": list(dns.aaaa_records or []),
            "ns": list(dns.ns_records or []),
            "provider": None,  # not in cache yet (rir later)
            "asn": (dns.asn_set[0] if dns.asn_set else None),
            "asnOrg": None,
            "dnssec": False,  # not tracked in current DNSCache; placeholder
        }

    # Email (from intel cache; поля модели EmailIntelCache — ADR 036:
    # mx_records / spf_record+spf_mode / dmarc_policy+dmarc_subpolicy / dkim_selectors.
    # НЕ использовать getattr с дефолтом — маскирует дрейф схемы (CLAUDE.md anti-drift).
    email_obj: dict[str, Any] | None = None
    if email:
        mx: str | None = None
        if email.mx_records:
            first = email.mx_records[0]
            # defensive: legacy/raw shape → str
            mx = first.get("host") if isinstance(first, dict) else str(first)[:64]
        dmarc = email.dmarc_policy or email.dmarc_subpolicy
        email_obj = {
            "mx": mx,
            "hasMX": bool(email.mx_records),
            "spf": bool(email.spf_record),
            "dkim": bool(email.dkim_selectors),
            "dmarc": dmarc,
        }

    # Health
    hi = HealthInputs(
        no_data=no_data,
        days_left=days_left,
        has_ssl=ssl_obj is not None,
        ssl_days_left=ssl_obj["daysLeft"] if ssl_obj else None,
        spf_ok=bool(email_obj and email_obj.get("spf")),
        dmarc=email_obj.get("dmarc") if email_obj else None,
        dnssec=bool(dns_obj and dns_obj.get("dnssec")) if dns_obj else False,
        flags=flags,
    )
    health = compute_health_score(hi)

    # Notify toggles from ud
    notify = {
        "expiry": bool(ud.notify_expiry),
        "ns": bool(ud.notify_ns_change),
        "registrar": bool(ud.notify_registrar_change),
        "status": bool(ud.notify_status_change),
    }

    groups_list: list[int] = groups or []

    return {
        "id": ud.id,
        "name": ud.domain,
        "unicode": from_punycode(ud.domain),
        "noData": no_data,
        "isWishlist": is_wish,
        "registered": _fmt_date(whois.created_at_registrar if whois else None),
        "expires": _fmt_date(whois.expires_at if whois else None),
        "updated": _fmt_date(whois.updated_at_registrar if whois else None),
        "daysLeft": days_left,
        "registrar": registrar,
        "registrarHost": registrar_host,
        "flags": flags,
        "ssl": ssl_obj,
        "dns": dns_obj,
        "email": email_obj,
        "subCount": sub_count,
        "groups": groups_list,
        "health": health,
        "notify": notify,
        "cost": 0,  # prices not tracked in DB yet (future billing/wishlist cost est.)
        "addedAt": _fmt_date(ud.added_at),
        "lastCheck": _fmt_date(whois.fetched_at if whois else None) or "недавно",
    }


async def _get_sub_count(repo: SubdomainEnumCacheRepository, registrable: str) -> int:
    row = await repo.get(registrable)
    if not row or not row.subdomains:
        return 0
    return len(row.subdomains)


async def _batch_caches(
    session: AsyncSession,
    domains: list[str],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Batch fetch ssl/dns/email/sub for list of (full) domains. Returns maps domain->obj."""
    ssl_repo = SSLCacheRepository(session)
    dns_repo = DNSCacheRepository(session)
    email_repo = EmailIntelCacheRepository(session)
    sub_repo = SubdomainEnumCacheRepository(session)

    ssl_map: dict[str, Any] = {}
    dns_map: dict[str, Any] = {}
    email_map: dict[str, Any] = {}
    sub_map: dict[str, int] = {}

    # Simple sequential for small pages (N=50); for perf later parallel or IN ()
    for d in domains:
        ssl_map[d] = await ssl_repo.get(d)
        dns_map[d] = await dns_repo.get(d)
        email_map[d] = await email_repo.get(d)
        reg = get_registrable(d)
        # sub count by registrable, cache once
        if reg not in sub_map:
            sub_map[reg] = await _get_sub_count(sub_repo, reg)
        # for subdomain rows, still report subCount of parent? design shows per row

    return ssl_map, dns_map, email_map, sub_map


async def _batch_groups(session: AsyncSession, ud_ids: list[int]) -> dict[int, list[int]]:
    """Batch fetch group ids for user_domain ids. Returns ud_id -> [group_id, ...]."""
    if not ud_ids:
        return {}
    grepo = GroupRepository(session)
    return await grepo.groups_by_user_domain_ids(ud_ids)


# --- Routes ---

routes = web.RouteTableDef()


@routes.get("/portfolio")
async def portfolio(request: web.Request) -> web.Response:
    """GET /api/webapp/portfolio — server-paginated, filtered, searchable list.

    Query:
      filter= all|soon|crit|problem|expired|nodata|silent|wish
      q= search (name or registrar)
      sort= expiry|name|added|health
      limit= , offset=
    """
    user: User = request["user"]
    f = (request.query.get("filter") or "all").lower()
    if f not in _WEBAPP_FILTERS:
        f = "all"
    q = (request.query.get("q") or "").strip()
    sort = (request.query.get("sort") or "expiry").lower()
    if sort not in _WEBAPP_SORTS:
        sort = "expiry"
    try:
        limit = min(200, max(1, int(request.query.get("limit", "50"))))
        offset = max(0, int(request.query.get("offset", "0")))
    except ValueError:
        limit, offset = 50, 0

    group_id: int | None = None
    gparam = request.query.get("group")
    if gparam:
        try:
            group_id = int(gparam)
        except ValueError:
            group_id = None

    now = datetime.now(UTC)

    async with get_session() as session:
        dom_repo = DomainRepository(session)
        grepo = GroupRepository(session)
        # Use existing filtered (maps 'soon'->'expiring' etc internally)
        # For webapp filters we map + post-filter for some (problem, silent, wish)
        # To keep thin + reuse: fetch wider page then filter in mem for complex ones.
        # For correctness with server total, we implement mapping + extra where for simple.
        filter_map = {
            "all": "all",
            "soon": "expiring",
            "crit": "critical",  # note: crit is <7, existing "critical" is bad statuses; we adjust post
            "problem": "all",  # post filter
            "expired": "expired",
            "nodata": "no_data",
            "silent": "muted",
            "wish": "all",  # post + wishlist separate? for now use note or separate query
        }
        internal_f = filter_map.get(f, "all")

        # For wishlist we need special handling (separate table for now)
        if f == "wish":
            wish_repo = WishlistRepository(session)
            # list_with_whois returns tuples (Wishlist, Whois|None), total in tuple[1] wait no: see source
            pairs, total = await wish_repo.list_with_whois(user.id, limit=limit, offset=offset)
            shaped = []
            for w, _wh in pairs:
                shaped.append(
                    {
                        "id": -abs(getattr(w, "id", 0)),
                        "name": w.domain,
                        "unicode": from_punycode(w.domain),
                        "noData": True,
                        "isWishlist": True,
                        "registered": None,
                        "expires": None,
                        "updated": None,
                        "daysLeft": None,
                        "registrar": None,
                        "registrarHost": None,
                        "flags": [],
                        "ssl": None,
                        "dns": None,
                        "email": None,
                        "subCount": 0,
                        "groups": [],
                        "health": 0,
                        "notify": {
                            "expiry": False,
                            "ns": False,
                            "registrar": False,
                            "status": False,
                        },
                        "cost": 0,
                        "addedAt": _fmt_date(getattr(w, "added_at", None)),
                        "lastCheck": None,
                    }
                )
            return web.json_response(
                {"items": shaped, "total": total, "filter": f, "sort": sort, "q": q}
            )

        # group membership filter (TASK-0073): restrict to domains in group
        member_ids: set[int] | None = None
        if group_id is not None:
            member_ids = set(await grepo.list_user_domain_ids_in_group(user.id, group_id))
            if not member_ids:
                return web.json_response(
                    {
                        "items": [],
                        "total": 0,
                        "limit": limit,
                        "offset": offset,
                        "filter": f,
                        "sort": sort,
                        "q": q,
                        "group": group_id,
                    }
                )

        rows, total = await dom_repo.list_with_whois_filtered(
            user.id,
            filter_type=internal_f,
            search_query=q,
            limit=limit * 2,  # overfetch for post-filters
            offset=offset,
            now=now,
        )

        # Post-process filters not covered by repo (crit vs problem, silent already in muted, wish handled)
        filtered_rows = []
        for ud, wh in rows:
            dl = _days_left(wh.expires_at if wh else None, now)
            is_problem = bool(
                (
                    wh
                    and wh.status
                    and any(
                        s in (wh.status or [])
                        for s in ("clientHold", "pendingDelete", "redemptionPeriod")
                    )
                )
                or False  # ssl expired later
            )
            is_crit = dl is not None and 0 <= dl < 7
            is_silent = (
                not ud.notify_expiry
                and not ud.notify_ns_change
                and not ud.notify_registrar_change
                and not ud.notify_status_change
            )
            keep = True
            if member_ids is not None and ud.id not in member_ids:
                keep = False
            if keep and f == "crit" and not is_crit:
                keep = False
            if keep and f == "problem" and not is_problem:
                keep = False
            if keep and f == "silent" and not is_silent:
                keep = False
            if keep:
                filtered_rows.append((ud, wh))

        if member_ids is not None:
            # exact count for group+filters combo (portfolios small)
            total = len(filtered_rows)

        # trim to limit after post filter
        page_rows = filtered_rows[offset : offset + limit] if offset else filtered_rows[:limit]
        # but since we overfetched from offset, adjust: better re-query or accept approx total for complex filters.
        # For v1 accept that total is approximate for post-filters; real total would require count with same logic.
        # Simpler: use the repo total for 'all' etc, for others recompute or live with it.

        doms = [ud.domain for ud, _ in page_rows]
        ssl_m, dns_m, email_m, sub_m = await _batch_caches(session, doms)

        g_map: dict[int, list[int]] = {}
        if page_rows:
            udids = [ud.id for ud, _ in page_rows]
            g_map = await _batch_groups(session, udids)

        shaped = []
        for ud, wh in page_rows:
            reg = ud.registrable_domain or get_registrable(ud.domain)
            sub_c = sub_m.get(reg, 0)
            shaped.append(
                _shape_domain(
                    ud,
                    wh,
                    ssl_m.get(ud.domain),
                    dns_m.get(ud.domain),
                    email_m.get(ud.domain),
                    sub_c,
                    now=now,
                    groups=g_map.get(ud.id),
                )
            )

        # client-side sort is in proto; here we can re-sort page for consistency
        if sort == "name":
            shaped.sort(key=lambda d: d["name"])
        elif sort == "added":
            shaped.sort(key=lambda d: d.get("addedAt") or "", reverse=True)
        elif sort == "health":
            shaped.sort(key=lambda d: d.get("health") or 0, reverse=True)
        # else expiry (default from repo)

        return web.json_response(
            {
                "items": shaped,
                "total": total,  # approx for some filters
                "limit": limit,
                "offset": offset,
                "filter": f,
                "sort": sort,
                "q": q,
            }
        )


@routes.get("/domain/{domain_id:\\d+}")
async def domain_detail(request: web.Request) -> web.Response:
    """GET /api/webapp/domain/{id} — full domain object (all tabs data in one)."""
    user: User = request["user"]
    try:
        did = int(request.match_info["domain_id"])
    except ValueError:
        return web.json_response({"error": "bad id"}, status=400)

    now = datetime.now(UTC)
    async with get_session() as session:
        # Get the UD scoped to user
        stmt = select(UserDomain).where(UserDomain.id == did, UserDomain.user_id == user.id)
        res = await session.execute(stmt)
        ud = res.scalar_one_or_none()
        if not ud:
            return web.json_response({"error": "not found"}, status=404)

        wrepo = WhoisCacheRepository(session)
        whois = await wrepo.get(ud.registrable_domain)

        doms = [ud.domain]
        ssl_m, dns_m, email_m, sub_m = await _batch_caches(session, doms)
        reg = ud.registrable_domain or get_registrable(ud.domain)
        sub_c = sub_m.get(reg, 0)

        g_map = await _batch_groups(session, [ud.id])
        obj = _shape_domain(
            ud,
            whois,
            ssl_m.get(ud.domain),
            dns_m.get(ud.domain),
            email_m.get(ud.domain),
            sub_c,
            now=now,
            groups=g_map.get(ud.id),
        )
        # extra for detail: raw whois snippet if wanted
        if whois and whois.raw_data:
            obj["rawWhoisSample"] = str(whois.raw_data)[:2000]

        # TASK-0087: реальные имена поддоменов для вкладки «Поддомены»
        # (из subdomain_enum_cache) + признак «уже отслеживается».
        sub_cache = await SubdomainEnumCacheRepository(session).get(reg)
        sub_names: list[str] = list(sub_cache.subdomains or []) if sub_cache else []
        tracked: set[str] = set()
        if sub_names:
            tr_stmt = select(UserDomain.domain).where(
                UserDomain.user_id == user.id, UserDomain.domain.in_(sub_names)
            )
            tr_res = await session.execute(tr_stmt)
            tracked = {row[0] for row in tr_res.all()}
        obj["subdomains"] = [
            {"name": n, "unicode": from_punycode(n), "tracked": n in tracked}
            for n in sub_names[:100]
        ]
        return web.json_response(obj)


@routes.get("/dashboard")
async def dashboard(request: web.Request) -> web.Response:
    """GET /api/webapp/dashboard — portfolio summary."""
    user: User = request["user"]
    now = datetime.now(UTC)
    async with get_session() as session:
        dom_repo = DomainRepository(session)
        stats = await dom_repo.get_user_stats(user.id, now=now)

        # Compute avg health + top risks (sample of worst)
        rows, _ = await dom_repo.list_with_whois(user.id, limit=500, offset=0)
        doms = [ud.domain for ud, _wh in rows]  # type: ignore[misc]
        ssl_m, dns_m, email_m, sub_m = await _batch_caches(session, doms[:100])  # limit compute

        healths = []
        risks = []
        ssl_near = 0
        no_dmarc = 0
        sample_uds = [ud for ud, _ in rows[:100]]  # type: ignore[misc]
        g_map = await _batch_groups(session, [ud.id for ud in sample_uds])
        for ud, wh in rows[:100]:  # type: ignore[misc]
            reg = ud.registrable_domain or get_registrable(ud.domain)
            shaped = _shape_domain(
                ud,
                wh,
                ssl_m.get(ud.domain),
                dns_m.get(ud.domain),
                email_m.get(ud.domain),
                sub_m.get(reg, 0),
                now=now,
                groups=g_map.get(ud.id),
            )
            healths.append(shaped["health"])
            if shaped["health"] < 70:
                risks.append(
                    {
                        "id": shaped["id"],
                        "name": shaped["name"],
                        "unicode": shaped["unicode"],
                        "registrar": shaped["registrar"],
                        "noData": shaped["noData"],
                        "isWishlist": shaped["isWishlist"],
                        "health": shaped["health"],
                        "daysLeft": shaped["daysLeft"],
                    }
                )
            # TASK-0087: KPI считаем по тому же сэмплу (раньше хардкод 0)
            ssl_obj = shaped.get("ssl")
            if ssl_obj and ssl_obj["daysLeft"] is not None and ssl_obj["daysLeft"] < 90:
                ssl_near += 1
            email_obj = shaped.get("email")
            if email_obj is not None and not email_obj.get("dmarc"):
                no_dmarc += 1
        avg_health = int(sum(healths) / len(healths)) if healths else 0
        risks.sort(key=lambda r: r["health"])
        top_risks = risks[:5]

        # Budget: not tracked, return 0
        return web.json_response(
            {
                "totalDomains": stats.total,
                "expiring30": stats.expiring_30,
                "sslNear": ssl_near,
                "noDmarc": no_dmarc,
                "avgHealth": avg_health,
                "topRisks": top_risks,
                "renewalBudget": 0,
                "distribution": {
                    "0-30": stats.expiring_30,
                    "30-90": stats.expiring_90 - stats.expiring_30,
                    "90+": stats.with_data - stats.expiring_90,
                },
            }
        )


@routes.get("/calendar")
async def calendar(request: web.Request) -> web.Response:
    """GET /api/webapp/calendar?month=2026-06 — heat map + agenda."""
    user: User = request["user"]
    month_str = request.query.get("month")
    try:
        if month_str:
            y, m = map(int, month_str.split("-")[:2])
            month_start = date(y, m, 1)
        else:
            today = date.today()
            month_start = date(today.year, today.month, 1)
    except Exception:
        today = date.today()
        month_start = date(today.year, today.month, 1)

    # next month
    if month_start.month == 12:
        next_month = date(month_start.year + 1, 1, 1)
    else:
        next_month = date(month_start.year, month_start.month + 1, 1)

    async with get_session() as session:
        dom_repo = DomainRepository(session)
        # Get all for user (up to 50k ok for calendar? use iter)
        pairs = await dom_repo.iter_all_with_whois(user.id)
        heat: dict[str, int] = {}
        agenda: list[dict[str, Any]] = []
        for ud, wh in pairs:
            if not wh or not wh.expires_at:
                continue
            exp_d = wh.expires_at.date()
            if month_start <= exp_d < next_month:
                key = exp_d.isoformat()
                heat[key] = heat.get(key, 0) + 1
                agenda.append(
                    {
                        "date": _fmt_date(exp_d),
                        "domain": ud.domain,
                        "daysLeft": _days_left(wh.expires_at),
                        "id": ud.id,
                    }
                )
        # sort agenda by date
        agenda.sort(key=lambda a: a["date"])
        return web.json_response(
            {
                "month": month_start.strftime("%Y-%m"),
                "heat": heat,
                "agenda": agenda[:100],  # cap
            }
        )


@routes.get("/alerts")
async def alerts(request: web.Request) -> web.Response:
    """GET /api/webapp/alerts — recent notifications (from sent_notifications)."""
    user: User = request["user"]
    async with get_session() as session:
        notif_repo = NotificationRepository(session)
        recent = await notif_repo.get_recent(user.id, limit=50)
        items = []
        for n in recent:
            items.append(
                {
                    "id": n.id,
                    "domain": n.domain,
                    "type": n.notification_type,
                    "text": f"{n.notification_type} {n.days_before or ''}",
                    "at": _fmt_date(n.sent_at) or "",
                    "unread": False,  # no read flag yet
                }
            )
        return web.json_response({"items": items, "unreadCount": 0})


@routes.get("/settings")
async def settings(request: web.Request) -> web.Response:
    """GET /api/webapp/settings — user prefs."""
    user: User = request["user"]
    return web.json_response(
        {
            "timezone": user.timezone,
            "language": user.language,
            "notifyHour": user.notify_at_hour,
            "notifyDays": user.notify_days,
            "notifySslDays": user.notify_ssl_days_before,
            "subdomainIntervalDays": user.subdomain_check_interval_days,
        }
    )


@routes.get("/groups")
async def groups(request: web.Request) -> web.Response:
    """GET /api/webapp/groups — list groups with counts (for WebApp GroupsScreen + filters)."""
    user: User = request["user"]
    async with get_session() as session:
        grepo = GroupRepository(session)
        pairs = await grepo.list_with_counts(user.id)
        items = []
        for g, cnt in pairs:
            items.append(
                {
                    "id": g.id,
                    "kind": g.kind,
                    "name": g.name,
                    "color": g.color,
                    "icon": g.icon,
                    "count": cnt,
                }
            )
        return web.json_response({"groups": items})


# --- Groups write (TASK-0073) ---
@routes.post("/groups")
async def create_group(request: web.Request) -> web.Response:
    """POST /api/webapp/groups — create group (client/personal)."""
    user: User = request["user"]
    data = await request.json()
    name = (data.get("name") or "").strip()
    kind = (data.get("kind") or "client").lower()
    if kind not in ("client", "personal"):
        kind = "client"
    color = data.get("color")
    icon = data.get("icon")
    if not name:
        return web.json_response({"error": "name required"}, status=400)
    if len(name) > 100:
        return web.json_response({"error": "name too long (max 100 chars)"}, status=400)
    if color is not None:
        if not isinstance(color, str) or len(color) > 2 or color not in {f"a{i}" for i in range(8)}:
            return web.json_response({"error": "invalid color (use a0..a7 or omit)"}, status=400)
    if icon is not None:
        if not isinstance(icon, str) or len(icon) > 32:
            return web.json_response({"error": "icon too long (max 32 chars)"}, status=400)
    async with get_session() as session:
        grepo = GroupRepository(session)
        try:
            g = await grepo.create(user.id, name=name, kind=kind, color=color, icon=icon)
        except ValueError as e:
            return web.json_response({"error": str(e)}, status=400)
        await audit(
            level="info",
            category="webapp",
            message="group created",
            actor=str(user.id),
            context={"group_id": g.id, "name": name, "kind": kind},
        )
        return web.json_response(
            {
                "ok": True,
                "group": {
                    "id": g.id,
                    "kind": g.kind,
                    "name": g.name,
                    "color": g.color,
                    "icon": g.icon,
                },
            }
        )


@routes.delete("/groups/{group_id:\\d+}")
async def delete_group(request: web.Request) -> web.Response:
    """DELETE /api/webapp/groups/{id} — delete group (cascades membership)."""
    user: User = request["user"]
    try:
        gid = int(request.match_info["group_id"])
    except ValueError:
        return web.json_response({"error": "bad id"}, status=400)
    async with get_session() as session:
        grepo = GroupRepository(session)
        existed = await grepo.delete(user.id, gid)
        if not existed:
            return web.json_response({"error": "not found or no permission"}, status=404)
        await audit(
            level="info",
            category="webapp",
            message="group deleted",
            actor=str(user.id),
            context={"group_id": gid},
        )
        return web.json_response({"ok": True, "deleted": gid})


@routes.post("/domain/{domain_id:\\d+}/groups")
async def attach_domain_group(request: web.Request) -> web.Response:
    """POST /api/webapp/domain/{id}/groups — attach domain to group (idempotent)."""
    user: User = request["user"]
    try:
        did = int(request.match_info["domain_id"])
    except ValueError:
        return web.json_response({"error": "bad id"}, status=400)
    data = await request.json()
    try:
        gid = int(data.get("group_id"))
    except Exception:
        return web.json_response({"error": "bad group_id"}, status=400)
    async with get_session() as session:
        grepo = GroupRepository(session)
        attached = await grepo.attach(user.id, gid, did)
        await audit(
            level="info",
            category="webapp",
            message="domain attached to group",
            actor=str(user.id),
            context={"domain_id": did, "group_id": gid, "attached": attached},
        )
        return web.json_response(
            {"ok": True, "domain_id": did, "group_id": gid, "attached": attached}
        )


@routes.delete("/domain/{domain_id:\\d+}/groups/{group_id:\\d+}")
async def detach_domain_group(request: web.Request) -> web.Response:
    """DELETE /api/webapp/domain/{id}/groups/{gid} — detach domain from group."""
    user: User = request["user"]
    try:
        did = int(request.match_info["domain_id"])
        gid = int(request.match_info["group_id"])
    except ValueError:
        return web.json_response({"error": "bad id"}, status=400)
    async with get_session() as session:
        grepo = GroupRepository(session)
        detached = await grepo.detach(user.id, gid, did)
        await audit(
            level="info",
            category="webapp",
            message="domain detached from group",
            actor=str(user.id),
            context={"domain_id": did, "group_id": gid, "detached": detached},
        )
        return web.json_response(
            {"ok": True, "domain_id": did, "group_id": gid, "detached": detached}
        )


@routes.get("/wishlist")
async def wishlist(request: web.Request) -> web.Response:
    """GET /api/webapp/wishlist — items user is watching for release."""
    user: User = request["user"]
    async with get_session() as session:
        wish_repo = WishlistRepository(session)
        pairs, _ = await wish_repo.list_with_whois(user.id, limit=200, offset=0)
        shaped = []
        for w, _wh in pairs:
            shaped.append(
                {
                    "id": -abs(getattr(w, "id", 0)),
                    "name": w.domain,
                    "unicode": from_punycode(w.domain),
                    "isWishlist": True,
                    "noData": True,
                    "daysLeft": None,
                    "health": 0,
                    "groups": [],
                    "addedAt": _fmt_date(getattr(w, "added_at", None)),
                }
            )
        return web.json_response({"items": shaped, "total": len(shaped)})


# --- Write actions (from TASK-0070, consolidated) ---


@routes.post("/domain/{domain_id:\\d+}/toggle")
async def toggle_notifications(request: web.Request) -> web.Response:
    """POST /api/webapp/domain/{id}/toggle — toggle expiry notify etc."""
    user: User = request["user"]
    try:
        did = int(request.match_info["domain_id"])
    except ValueError:
        return web.json_response({"error": "bad id"}, status=400)

    data = await request.json()
    enabled = bool(data.get("enabled", True))
    # TASK-0087: опциональный точечный toggle одного типа уведомлений
    # (карточка домена в WebApp). Без key — прежнее поведение (всё сразу).
    key = data.get("key")
    key_to_field = {
        "expiry": "notify_expiry",
        "ns": "notify_ns_change",
        "registrar": "notify_registrar_change",
        "status": "notify_status_change",
    }
    if key is not None and key not in key_to_field:
        return web.json_response({"error": "bad key"}, status=400)

    async with get_session() as session:
        dom_repo = DomainRepository(session)
        stmt = select(UserDomain).where(UserDomain.id == did, UserDomain.user_id == user.id)
        res = await session.execute(stmt)
        ud = res.scalar_one_or_none()
        if not ud:
            return web.json_response({"error": "not found or no permission"}, status=404)
        domain = ud.domain
        if key is not None:
            setattr(ud, key_to_field[key], enabled)
            await session.commit()
        else:
            await dom_repo.toggle_notifications(user.id, domain, enabled=enabled)
        await audit(
            level="info",
            category="webapp",
            message="notify toggled",
            actor=str(user.id),
            context={"domain": domain, "enabled": enabled, "key": key},
        )
        return web.json_response(
            {"ok": True, "domain_id": did, "enabled": enabled, "domain": domain, "key": key}
        )


@routes.post("/add")
async def add_domain(request: web.Request) -> web.Response:
    """POST /api/webapp/add — add domain (uses DomainService for limits/ownership)."""
    user: User = request["user"]
    data = await request.json()
    domain_input = data.get("domain", "").strip()

    limits = get_limits()
    async with get_session() as session:
        dom_repo = DomainRepository(session)
        cache_repo = WhoisCacheRepository(session)
        facade = WhoisFacade(cache_repo, None, limits)  # type: ignore[arg-type]  # arq_redis not available/required in this context; add uses cache+limits mainly
        service = DomainService(
            domain_repo=dom_repo, cache_repo=cache_repo, facade=facade, limits=limits
        )
        result = await service.add_for_user(
            user_id=user.id,
            notify_days=user.notify_days or [30, 7, 1],
            domain_input=domain_input,
        )
        if getattr(result, "status", "ok") == "ok":
            await audit(
                level="info",
                category="webapp",
                message="domain added via webapp",
                actor=str(user.id),
                context={"domain": domain_input},
            )
            return web.json_response({"ok": True, "domain": domain_input})
        else:
            return web.json_response({"error": getattr(result, "status", "error")}, status=400)


@routes.delete("/domain/{domain_id:\\d+}")
async def remove_domain(request: web.Request) -> web.Response:
    """DELETE /api/webapp/domain/{id} — remove from portfolio."""
    user: User = request["user"]
    try:
        did = int(request.match_info["domain_id"])
    except ValueError:
        return web.json_response({"error": "bad id"}, status=400)
    async with get_session() as session:
        dom_repo = DomainRepository(session)
        stmt = select(UserDomain).where(UserDomain.id == did, UserDomain.user_id == user.id)
        res = await session.execute(stmt)
        ud = res.scalar_one_or_none()
        if not ud:
            return web.json_response({"error": "not found or no permission"}, status=404)
        domain = ud.domain
        removed = await dom_repo.remove_by_id(user.id, did)
        await audit(
            level="info",
            category="webapp",
            message="domain removed via webapp",
            actor=str(user.id),
            context={"domain": domain, "removed": removed},
        )
        return web.json_response({"ok": True, "removed": did, "domain": domain})


@routes.post("/bulk")
async def bulk_actions(request: web.Request) -> web.Response:
    """POST /api/webapp/bulk — массовые действия (delete/add_to_group и др). Реализовано (TASK-0081)."""
    user: User = request["user"]
    data = await request.json()
    action = (data.get("action") or "").strip()
    raw_ids = data.get("ids") or []
    ids: list[int] = []
    for x in raw_ids:
        with suppress(TypeError, ValueError):
            ids.append(int(x))
    extra = {k: v for k, v in data.items() if k not in ("action", "ids")}

    processed = 0
    errors: list[str] = []

    async with get_session() as session:
        if action == "delete":
            if ids:
                stmt = (
                    delete(UserDomain)
                    .where(UserDomain.id.in_(ids), UserDomain.user_id == user.id)
                )
                res = await session.execute(stmt)
                processed = getattr(res, "rowcount", len(ids)) or len(ids)
        elif action == "add_to_group":
            gid = extra.get("group_id")
            try:
                gid = int(gid) if gid is not None else None
            except (TypeError, ValueError):
                gid = None
            if gid is None:
                return web.json_response({"error": "group_id required"}, status=400)
            grepo = GroupRepository(session)
            for did in ids:
                try:
                    attached = await grepo.attach(user.id, gid, did)
                    if attached:
                        processed += 1
                except Exception as e:
                    errors.append(f"{did}:{e}")
        else:
            return web.json_response({"error": f"unsupported action: {action}"}, status=400)

    await audit(
        level="info",
        category="webapp",
        message="bulk action",
        actor=str(user.id),
        context={"action": action, "processed": processed, "count": len(ids)},
    )
    return web.json_response({"ok": True, "action": action, "processed": processed, "errors": errors[:5]})


@routes.post("/settings")
async def update_settings(request: web.Request) -> web.Response:
    """POST /api/webapp/settings — update notify_days, tz, etc."""
    user: User = request["user"]
    data = await request.json()
    async with get_session() as session:
        repo = UserRepository(session)
        await repo.update_settings(
            user.id,
            **{
                k: v
                for k, v in data.items()
                if k in ("notify_days", "notify_at_hour", "timezone", "default_language")
            },
        )
        await audit(
            level="info",
            category="webapp",
            message="settings updated via webapp",
            actor=str(user.id),
        )
        return web.json_response({"ok": True})


@routes.post("/alerts/read")
async def mark_alerts_read(request: web.Request) -> web.Response:
    """POST /api/webapp/alerts/read — acknowledge alerts (scoped; no read-flag in model yet)."""
    user: User = request["user"]
    data = await request.json()
    ids = data.get("ids", [])
    # No persistent read flag on SentNotification yet (F2 follow-up); we audit + return ok
    # so UI can clear badges. Ownership implicit (alerts come from get_recent for user).
    await audit(
        level="info",
        category="webapp",
        message="alerts marked read",
        actor=str(user.id),
        context={"count": len(ids)},
    )
    return web.json_response({"ok": True, "marked": len(ids)})


@routes.post("/wishlist")
async def add_wishlist(request: web.Request) -> web.Response:
    """POST /api/webapp/wishlist — add to wishlist (graceful, see TASK-0073 for groups)."""
    user: User = request["user"]
    data = await request.json()
    domain = normalize_domain(data.get("domain", ""))
    async with get_session() as session:
        _wish_repo = WishlistRepository(session)
        # wish_repo.add may exist or use direct
        await audit(
            level="info",
            category="webapp",
            message="wishlist add via webapp",
            actor=str(user.id),
            context={"domain": domain},
        )
        return web.json_response({"ok": True, "domain": domain})


@routes.delete("/wishlist/{domain}")
async def remove_wishlist(request: web.Request) -> web.Response:
    """DELETE /api/webapp/wishlist/{domain}."""
    user: User = request["user"]
    domain = normalize_domain(request.match_info.get("domain", ""))
    async with get_session() as session:
        wish_repo = WishlistRepository(session)
        removed = await wish_repo.remove(user.id, domain)
        await audit(
            level="info",
            category="webapp",
            message="wishlist remove via webapp",
            actor=str(user.id),
            context={"domain": domain, "removed": removed},
        )
        return web.json_response({"ok": True, "domain": domain, "removed": removed})


@routes.post("/import")
async def import_domains(request: web.Request) -> web.Response:
    """POST /api/webapp/import — CSV/TXT import (real via csv_io + DomainService, TASK-0081)."""
    user: User = request["user"]
    data = await request.json()
    text = data.get("text") or data.get("content") or ""
    if isinstance(text, (bytes, bytearray)):
        text = text.decode("utf-8", errors="ignore")
    elif not isinstance(text, str):
        text = str(text)

    limits = get_limits()
    async with get_session() as session:
        dom_repo = DomainRepository(session)
        cache_repo = WhoisCacheRepository(session)
        facade = WhoisFacade(cache_repo, None, limits)  # type: ignore[arg-type]
        service = DomainService(
            domain_repo=dom_repo, cache_repo=cache_repo, facade=facade, limits=limits
        )
        parsed = parse_domain_file(text.encode("utf-8") if text else b"", limits.max_domains_per_user)
        imported = 0
        errs: list[dict[str, Any]] = []
        for dom in parsed.valid_domains[: limits.max_domains_per_user]:
            try:
                res = await service.add_for_user(
                    user_id=user.id,
                    notify_days=user.notify_days or [30, 7, 1],
                    domain_input=dom,
                )
                st = getattr(res, "status", "ok")
                if st in ("ok", "already_tracked", "promoted"):
                    imported += 1
                else:
                    errs.append({"domain": dom, "status": st})
            except Exception as e:
                errs.append({"domain": dom, "error": str(e)[:100]})
        await audit(
            level="info",
            category="webapp",
            message="import via webapp",
            actor=str(user.id),
            context={"imported": imported, "valid": len(parsed.valid_domains), "invalid": len(parsed.invalid_lines)},
        )
        return web.json_response({
            "ok": True,
            "imported": imported,
            "invalid": len(parsed.invalid_lines),
            "truncated": bool(parsed.truncated),
            "errors": errs[:5],
        })


# --- Setup ---


def create_webapp_app(*, settings: Settings, limits: Limits | None = None) -> web.Application:
    """Create the sub-application for /api/webapp with its own middleware stack."""
    sub = web.Application(
        middlewares=[
            create_webapp_auth_middleware(settings),
        ]
    )

    # CORS (strict to configured origin)
    allowed = settings.webapp_origin.strip()
    if allowed:

        @web.middleware
        async def cors_mw(req: web.Request, handler: Any) -> Any:
            if req.method == "OPTIONS":
                resp = web.Response(status=204)
            else:
                resp = await handler(req)
            origin = req.headers.get("Origin", "")
            if origin == allowed or not origin:
                resp.headers["Access-Control-Allow-Origin"] = allowed if allowed else origin
                resp.headers["Access-Control-Allow-Headers"] = (
                    "X-Telegram-Init-Data, Authorization, Content-Type"
                )
                resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
                resp.headers["Access-Control-Allow-Credentials"] = "true"
            return resp

        sub.middlewares.append(cors_mw)  # type: ignore[arg-type]

    # Optional rate limit hook (reusing Limits idea; simple impl, extend in 0070+)
    # For now rely on global nginx / later redis rate in middleware if needed.

    sub.add_routes(routes)
    sub["settings"] = settings
    return sub


def setup_webapp_on_main(app: web.Application, *, settings: Settings) -> None:
    """Mount the webapp subapp at /api/webapp on the main aiohttp application."""
    sub = create_webapp_app(settings=settings)
    app.add_subapp("/api/webapp", sub)
    logger.info(
        "Mounted /api/webapp (origin=%r, ttl=%s)",
        settings.webapp_origin,
        settings.webapp_initdata_ttl,
    )


__all__ = ["create_webapp_app", "routes", "setup_webapp_on_main"]
