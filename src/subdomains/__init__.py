"""Subdomain enumeration через crt.sh (ADR 037).

On-demand обнаружение поддоменов через CT-логи. Результат кэшируется
в ``subdomain_enum_cache`` (TASK-0022) для повторных вызовов ``/subdomains``.

Пакет содержит:
- Клиент к crt.sh API
- Парсер/нормализацию выдачи
- Adaptive TTL scheduler
"""

from __future__ import annotations

__all__ = []
