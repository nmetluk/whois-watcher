# SESSION-0046 — Тесты deep-email: format_email_deep + кнопка «Глубокий e-mail» (TASK-0046)

**Дата:** 2026-06-02  
**Таск:** TASK-0046  
**Ветка:** task/0046-deep-email-button-tests  
**PR:** (будет)  
**Исполнитель:** Claude (Grok)

---

## Цель

Добавить юнит-тесты для `format_email_deep` (в formatters.py) и хэндлера кнопки «✉️ Глубокий e-mail» (`_show_deep_email_from_whois_card` в whois.py), которые ушли в main в TASK-0041 без тестового покрытия.

## План (по задаче)

1. `tests/unit/test_format_email_deep.py` (новый файл):
   - `format_email_deep(None)` → `deep_email.no_data`
   - Полный кэш со всеми секциями → заголовки, значения экранированы (`html.escape`)
   - SPF: `exceeds_limit=True` → ⚠️; усечение >8 sources → "(+N)"
   - Пустые секции (None) → секция пропускается или "не настроено"
   - DANE mixed host_tlsa → правильные иконки

2. `tests/unit/test_whois_deep_email_button.py` (новый файл):
   - Свежий кэш (`next_check_at > now`) → рендер из кэша, без enqueue
   - Пусто/протух → `enqueue_job("check_email_deep")` + сообщение «ищу…»
   - Guard: callback_data ≤ 64 байт для `WhoisAction(action="deep_email", ...)`
   - Моки со `spec`/`autospec` (CallbackQuery, Message, User, EmailDeepCache)

3. Обновить handoff/INDEX.md и TASK-0046 после выполнения.

## Статус (2026-06-02)

**Готово:**

- Созданы два тестовых файла по точной спецификации из TASK-0046:
  - `tests/unit/test_format_email_deep.py` (10 тестов)
  - `tests/unit/test_whois_deep_email_button.py`
- Все тесты проходят (10/10).
- Соблюдён стиль проекта (MagicMock(spec=...), anti-drift, autospec).
- ruff / black чисто.

Ветка: `task/0046-deep-email-button-tests`

Готов к PR и ревью.
