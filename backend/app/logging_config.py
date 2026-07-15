"""structlog configuration."""
from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=level, stream=sys.stdout, format="%(message)s")
    # SECURITY: httpx logs the full request URL at INFO ("HTTP Request: GET
    # http://<switch>/cgi/...?..."). Several switch CGIs carry credentials in
    # the query string by firmware design (device-passwords, stacking), so
    # httpx INFO logging would persist cleartext switch passwords into
    # container logs. Cap both loggers at WARNING — never lower these without
    # adding a redaction filter for the credential query params first
    # (_UserPasswd, _UserPasswd2, _RootPasswd, _RootPasswd2, passwd).
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )
