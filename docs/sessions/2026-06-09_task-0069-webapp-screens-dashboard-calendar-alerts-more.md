# SESSION-0069 — WebApp экраны: дашборд + календарь + алерты + «Ещё»

**Дата:** 2026-06-09 · **Таск:** TASK-0069 · **Ветка:** task/0069-webapp-screens-dashboard-calendar-alerts-more
· **Исполнитель:** Grok

## Задача
Реализовать 4 экрана по дизайну: Dashboard (hero Ring, кликабельные KPI, распределение, бюджет, топ-риски), Calendar (сетка Пн-первый, теплокарта, навигация, агенда, iCal stub), Alerts (чипы, строки по severity, badge), More (профиль, секции Groups/Wishlist/Stats/Import/Settings + theme toggle, sub stubs).

На базе API 0066 и foundation 0067/68.

## Выполнено
- Дополнен api.ts: fetchDashboard, fetchCalendar, fetchAlerts, fetchSettings, fetchWishlist, fetchGroups.
- lib/domain.ts, components (Icon, Ring, DomainRow) — примитивы.
- src/screens/:
  - DashboardScreen: hero с Ring, 2x2 KPI (клик → list filter), distbar, бюджет, топ-риски (DomainRow).
  - CalendarScreen: месяц сетка (Пн-первый), heat, навигация, sel day agenda, iCal stub, month list.
  - AlertsScreen: чипы (all/unread/expiry/ssl/changes), severity иконки, unread badge.
  - MoreScreen: профиль, секции (Groups/Wishlist/Stats/Import/Export/Settings), dark toggle; sub-stubs (Groups, Wishlist, Stats, Import, Settings, Add).
- ListScreen + DomainScreen (минимальные из 68 для полноты).
- App.tsx: полная 5-tab навигация + стек для sub-screens (groups, wishlist и т.д.), интеграция всех, go() для фильтров из дашборда, theme sync.
- Стили восстановлены (tokens + tg-chrome + kpi etc).
- Сборка чистая (tsc + vite).

## Проверки
- `npm run build` ✅
- Мок + реальные API вызовы (с catch на demo).
- KPI кликабельны, календарь правильная раскладка, алерты с фильтрами, More с тогглом темы.
- Нет групп (stub), действия read-only (0070).

## Что осталось / след
- Полная интеграция с реальными данными из /dashboard etc (типы).
- iCal генерация (можно на бэке).
- Тесты компонентов, real TG тест (с кнопкой в боте).
- 0070 для writes (импорт, тогглы, прочитать алерты, add).

## PR
https://github.com/nmetluk/whois-watcher/pull/47

Отчёт + handoff in_review.
