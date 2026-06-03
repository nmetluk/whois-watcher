import React, { useCallback, useEffect, useRef, useState } from "react";
import { Icon } from "./components/Icon";
import { initTelegram, syncTheme, setupBackButton, setupMainButton, getTg } from "./lib/telegram";
import type { PortfolioResponse, WebAppDomain } from "./lib/api";
import { fetchPortfolio } from "./lib/api";

/**
 * TASK-0067 foundation:
 * - Vite React TS
 * - PIN Voice tokens + TG chrome CSS (ported values)
 * - Telegram.WebApp integration (theme, Main/BackButton, expand)
 * - 5 tabs + screen stack navigation (no react-router, state like prototype)
 * - API client carrying initData
 * - Buildable without prototype cruft (no phone frame, no unpkg)
 *
 * Screens are stubs. Real content + interactions in TASK-0068/0069.
 */

const TABS = [
  { id: "list", icon: "language", label: "Домены" },
  { id: "dashboard", icon: "monitoring", label: "Дашборд" },
  { id: "calendar", icon: "calendar_month", label: "Календарь" },
  { id: "alerts", icon: "notifications", label: "Алерты" },
  { id: "more", icon: "menu", label: "Ещё" },
] as const;

type TabId = (typeof TABS)[number]["id"];
type StackItem = { type: string; id?: number | string };

function App() {
  const [, setTheme] = useState<"light" | "dark">("light");
  const [tab, setTab] = useState<TabId>("list");
  const [stack, setStack] = useState<StackItem[]>([]);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [sheet, setSheet] = useState<any>(null);
  const [toastMsg, setToastMsg] = useState<{ msg: string; icon?: string } | null>(null);

  // List state (demo)
  const [st, setSt] = useState({
    query: "",
    filter: "all",
    sort: "expiry",
    selMode: false,
    sel: new Set<number>(),
  });
  const [domains, setDomains] = useState<WebAppDomain[]>([]);
  const [portfolioMeta, setPortfolioMeta] = useState<{ total: number; loading: boolean }>({
    total: 0,
    loading: false,
  });

  const bodyRef = useRef<HTMLDivElement>(null);
  const { isTelegram } = initTelegram();

  // Theme sync with Telegram
  useEffect(() => {
    syncTheme(setTheme);
  }, []);

  // BackButton handling (TG native)
  const top = stack[stack.length - 1] || null;
  const showBack = !!top;

  const back = React.useCallback(() => setStack((p) => p.slice(0, -1)), []);

  useEffect(() => {
    const handleBack = () => back();
    setupBackButton(handleBack, showBack);
    return () => {
      const tg = getTg();
      if (tg?.BackButton) tg.BackButton.hide();
    };
  }, [showBack, back]);

  // Toast helper
  const toast = useCallback((msg: string, icon = "check_circle") => {
    setToastMsg({ msg, icon });
    const w = window as unknown as { __toastT?: number };
    window.clearTimeout(w.__toastT);
    w.__toastT = window.setTimeout(() => setToastMsg(null), 2200);
  }, []);

  // Navigation
  const push = (s: StackItem) => {
    setStack((p) => [...p, s]);
    if (bodyRef.current) bodyRef.current.scrollTop = 0;
  };
  const goTab = (newTab: TabId) => {
    setStack([]);
    setTab(newTab);
  };

  const openDomain = (d: WebAppDomain) => push({ type: "domain", id: d.id });

  // Demo data load from real API (uses initData)
  const loadPortfolio = React.useCallback(async (override?: Partial<typeof st>) => {
    const params = { ...st, ...override };
    setPortfolioMeta((m) => ({ ...m, loading: true }));
    try {
      const res: PortfolioResponse = await fetchPortfolio({
        filter: params.filter,
        q: params.query,
        sort: params.sort,
        limit: 50,
      });
      setDomains(res.items);
      setPortfolioMeta({ total: res.total, loading: false });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      console.warn("API load failed (expected if no backend or outside TG):", msg);
      // Fallback demo data so UI is visible
      setDomains([
        {
          id: 1,
          name: "example.com",
          unicode: "example.com",
          noData: false,
          isWishlist: false,
          daysLeft: 12,
          registrar: "Example Registrar",
          flags: [],
          health: 87,
          subCount: 3,
          groups: [],
          notify: { expiry: true, ns: false, registrar: true, status: true },
          cost: 0,
          addedAt: "01.01.2025",
        } as unknown as WebAppDomain,
      ]);
      setPortfolioMeta({ total: 1, loading: false });
      toast("Demo data (backend not reachable in this env)");
    }
  }, [st, toast]);

  // Initial load (bootstrap only)
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadPortfolio();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // MainButton demo (TG native when possible)
  const currentMain = React.useMemo(() => {
    if (top?.type === "domain") {
      return {
        text: "Обновить данные",
        onClick: () => toast("Refresh requested (demo)"),
        visible: true,
      };
    }
    if (tab === "list" && st.selMode && st.sel.size > 0) {
      return {
        text: `Действия · ${st.sel.size}`,
        onClick: () => setSheet({ type: "bulk" }),
        visible: true,
      };
    }
    return null;
  }, [top, tab, st.selMode, st.sel.size, toast]);

  useEffect(() => {
    if (currentMain) {
      setupMainButton({
        text: currentMain.text,
        onClick: currentMain.onClick,
        visible: currentMain.visible,
      });
    } else {
      const tg = getTg();
      tg?.MainButton?.hide();
    }
  }, [currentMain]);

  // Header title logic (simplified from prototype)
  let headerTitle: string = TABS.find((t) => t.id === tab)!.label;
  let headerSub: React.ReactNode = null;
  let showMenu = false;

  if (top?.type === "domain") {
    headerTitle = "Домен";
    const d = domains.find((x) => x.id === top.id);
    if (d) {
      headerSub = d.daysLeft != null ? `${d.daysLeft} дн.` : "—";
    }
    showMenu = true;
  }

  const showTabbar = !top;
  const showFab = !top && tab === "list" && !st.selMode;

  // Dummy screen content renderers (foundation only)
  function renderBody() {
    if (top?.type === "domain") {
      const d = domains.find((x) => x.id === top.id);
      return (
        <div className="screen-body tg-pad">
          <div className="tg-card">
            <div style={{ fontSize: 22, fontWeight: 700 }}>{d?.name}</div>
            <div>Health: {d?.health}</div>
            <div>Истекает: {d?.daysLeft} дней</div>
          </div>
          <div className="tg-card">
            <b>Обзор (stub)</b>
            <p>Полные данные придут из /api/webapp/domain/{top.id} в TASK-0068.</p>
          </div>
          <button className="pv-btn" onClick={() => back()}>
            Назад
          </button>
        </div>
      );
    }

    if (tab === "list") {
      return (
        <div className="screen-body">
          <div className="tg-search-sticky">
            <input
              className="tg-search"
              placeholder="Поиск домена или регистратора…"
              value={st.query}
              onChange={(e) => {
                const q = e.target.value;
                setSt((s) => ({ ...s, query: q }));
                loadPortfolio({ query: q });
              }}
            />
          </div>

          <div className="tg-filters">
            {["all", "soon", "crit", "problem", "expired", "nodata", "silent", "wish"].map((f) => (
              <button
                key={f}
                className={`tg-chip ${st.filter === f ? "active" : ""}`}
                onClick={() => {
                  setSt((s) => ({ ...s, filter: f }));
                  loadPortfolio({ filter: f });
                }}
              >
                {f}
              </button>
            ))}
          </div>

          <div className="tg-list-head">
            {portfolioMeta.loading ? "Загрузка..." : `Всего: ${portfolioMeta.total}`}
          </div>

          {domains.length === 0 && <div className="tg-pad">Ничего не найдено (или demo)</div>}

          {domains.map((d) => (
            <div key={d.id} className="tg-drow" onClick={() => openDomain(d)}>
              <div
                className="tg-puck"
                style={{
                  background: d.isWishlist
                    ? "var(--pv-violet)"
                    : d.daysLeft != null && d.daysLeft < 7
                    ? "var(--pv-red)"
                    : "var(--pv-green)",
                  color: "#fff",
                }}
              >
                {d.daysLeft ?? "—"}
              </div>
              <div className="tg-drow-info">
                <div className="tg-drow-name">
                  {d.unicode}
                  {!d.notify.expiry && <Icon name="notifications_off" />}
                </div>
                <div className="tg-drow-sub">
                  {d.registrar || "—"} · {d.daysLeft != null ? `через ${d.daysLeft} дн.` : "без данных"}
                </div>
              </div>
              <div style={{ textAlign: "right", fontSize: 12 }}>
                <div>♥ {d.health}</div>
                <div style={{ color: "var(--pv-fg-subtle)" }}>{d.subCount} подд.</div>
              </div>
            </div>
          ))}

          <div className="tg-pad" style={{ fontSize: 12, color: "var(--pv-fg-muted)" }}>
            Foundation stub. Полный список + серверная пагинация + мультивыбор — в следующих тасках.
            <br />
            <button className="pv-btn secondary" style={{ marginTop: 8 }} onClick={() => loadPortfolio()}>
              Перезагрузить из API
            </button>
          </div>
        </div>
      );
    }

    // Other tabs stubs
    return (
      <div className="screen-body tg-pad">
        <div className="tg-card">
          <h3 style={{ marginTop: 0 }}>{headerTitle} (stub)</h3>
          <p>
            Экран-заглушка для демонстрации навигации и chrome.
            <br />
            Реализация в TASK-0068 (список+карточка) и TASK-0069 (дашборд, календарь, алерты, ещё).
          </p>
          <button className="pv-btn" onClick={() => toast("Действие (demo)")}>
            Тестовое действие
          </button>
        </div>

        {tab === "more" && (
          <div className="tg-card">
            <div onClick={() => push({ type: "settings" })} style={{ padding: "8px 0", cursor: "pointer" }}>
              Настройки →
            </div>
            <div onClick={() => push({ type: "wishlist" })} style={{ padding: "8px 0", cursor: "pointer" }}>
              Wishlist →
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="screen" style={{ minHeight: "100dvh", display: "flex", flexDirection: "column" }}>
      {/* Header */}
      <div className={`tg-header ${!showTabbar ? "center" : ""}`}>
        {showBack ? (
          <button className="tg-hbtn" onClick={back} aria-label="Назад">
            <Icon name="arrow_back" />
          </button>
        ) : (
          <button className="tg-hbtn" onClick={() => toast("Меню (stub)")} aria-label="Меню">
            <Icon name="menu" />
          </button>
        )}

        <div className="tg-htitle">
          <b>{String(headerTitle)}</b>
          {headerSub && <span>{headerSub}</span>}
        </div>

        {showMenu && (
          <button className="tg-hbtn" onClick={() => setSheet({ type: "domain-menu" })}>
            <Icon name="more_vert" />
          </button>
        )}
      </div>

      {/* Body */}
      <div ref={bodyRef} className="screen-body" style={{ flex: 1, overflow: "auto" }}>
        {renderBody()}
      </div>

      {/* Tab bar */}
      {showTabbar && (
        <div className="tg-tabbar">
          {TABS.map((t) => (
            <button
              key={t.id}
              className={`tg-tab ${tab === t.id ? "active" : ""}`}
              onClick={() => goTab(t.id)}
            >
              <Icon name={t.icon} />
              <span>{t.label}</span>
            </button>
          ))}
        </div>
      )}

      {/* FAB */}
      {showFab && (
        <button className="tg-fab" onClick={() => push({ type: "add" })} aria-label="Добавить">
          <Icon name="add" />
        </button>
      )}

      {/* MainButton (controlled via TG or visible custom fallback) */}
      {!isTelegram && currentMain && (
        <button
          className={`tg-mainbtn ${currentMain.text.includes("Действия") ? "" : ""}`}
          onClick={currentMain.onClick}
        >
          {currentMain.text}
        </button>
      )}

      {/* Sheets */}
      {sheet && (
        <div className="tg-sheet-mask" onClick={() => setSheet(null)}>
          <div className="tg-sheet" onClick={(e) => e.stopPropagation()}>
            <div className="tg-sheet-grab" />
            <div className="tg-pad">
              {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
              <b>Sheet: {(sheet as any)?.type || 'unknown'}</b>
              <p>Действия и массовые операции — в TASK-0070.</p>
              <button className="pv-btn secondary" onClick={() => setSheet(null)}>
                Закрыть
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Toast */}
      {toastMsg && (
        <div className="tg-toast">
          <Icon name={toastMsg.icon || "info"} />
          {toastMsg.msg}
        </div>
      )}

      <div style={{ fontSize: 10, opacity: 0.4, textAlign: "center", padding: 4 }}>
        WebApp foundation • {isTelegram ? "Telegram" : "dev mode"} • initData length: {getTg()?.initData?.length || 0}
      </div>
    </div>
  );
}

export default App;
