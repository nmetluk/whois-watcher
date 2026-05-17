"""SSL certificate monitoring subsystem (Этап 12, ADR 030).

Параллельная подсистема к ``src.whois`` для мониторинга X.509-сертификатов:

- ``types.SSLCertificate`` / ``SSLError`` — доменные типы
- ``client.fetch_certificate`` — async TLS-клиент через cryptography
- ``scheduler.calculate_next_ssl_check`` — adaptive TTL
- ``diff.compute_ssl_diff`` — определение изменений между запусками
"""
