# SESSION-0068 — WebApp: список доменов + карточка домена

**Дата:** 2026-06-09 · **Таск:** TASK-0068 · **Ветка:** task/0068-webapp-screens-list-domain
· **Исполнитель:** Grok

## Задача
Воссоздать экраны List (поиск, фильтры-чипы со счётчиками, сортировки, DomainRow, мультивыбор) и Domain card (вкладки overview/whois/ssl/dns/email/subs, health Ring, IRow, тогглы UI) на базе API из 0066 и foundation из 0067. Виртуализация/пагинация, примитивы из core.

## Выполнено
- Портированы примитивы: statusOf, daysText, Ring, Check, GroupTag (stub), IRow, DomainRow, Icon (enhanced).
- ListScreen: липкий поиск, 8 фильтров (с client counters), 4 сортировки (sheet), DomainRow с паками, мультивыбор, "load more" (серверная пагинация + API filter/q/sort), пустое состояние.
- DomainScreen: 6 вкладок, hero с Ring + статус + days, quick actions, health factors (с Check), уведомления (UI тогглы, disabled), WHOIS/SSL/DNS/Email/Subs stubs с IRow.
- App.tsx обновлён: использует <ListScreen/> и <DomainScreen/>, chrome (header/tabbar), tg hooks, toast, навигация стеком.
- Стили дополнены/восстановлены (tokens + tg-chrome).
- Типы WebAppDomain выровнены.
- Нет групп (пусто, как в 0073), тогглы read-only (пишется в 0070).
- `npm run build` + lint чистые.

## Изменённые/новые файлы (webapp/)
- src/lib/{api.ts,domain.ts,telegram.ts}
- src/components/{Icon,Ring,Check,GroupTag,IRow,DomainRow}.tsx
- src/screens/{ListScreen,DomainScreen}.tsx
- src/{App,main,index}.tsx + styles/*
- package etc (reboot)

## Проверки
- vite build ✅
- eslint ✅
- typecheck (в build) ✅
- Рендер на мок/демо + реальный API вызов (с фолбэком).
- statusOf совпадает с дизайном.

## Что осталось
- Полная виртуализация (react-window или custom для 50k) — сейчас пагинация + load more (приемлемо для mobile).
- Реальные данные в карточке из fetchDomain.
- Группировка в списке (статус работает частично).
- Real TG тест + скрины в следующем отчёте (0069/audit).
- Связь с write API в 0070.

## PR
https://github.com/nmetluk/whois-watcher/pull/46 (after push)

Per handoff: report + status in_review.
