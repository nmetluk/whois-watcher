"""Расширенный DNS-отчёт (ADR 044): on-demand профессиональный анализ
всех DNS-записей домена с выдачей в виде текстового файла."""

from src.dns_report.client import fetch_dns_report
from src.dns_report.formatter import format_dns_report
from src.dns_report.types import DnsRecord, DnsReportError, DnsReportResult

__all__ = [
    "DnsRecord",
    "DnsReportError",
    "DnsReportResult",
    "fetch_dns_report",
    "format_dns_report",
]
