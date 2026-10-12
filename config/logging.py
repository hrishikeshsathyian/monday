"""Process-wide logging setup, called once by each service's entry point."""

import logging

from config.settings import ENV


def setup_logging() -> None:
    """Configure root logging and silence noisy HTTP client libraries."""
    logging.basicConfig(
        level=logging.INFO,
        format=f"[{ENV.upper()}] %(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # httpx/httpcore log every request used by supabase and python-telegram-bot, too noisy
    logging.getLogger("httpx").disabled = True
    logging.getLogger("httpcore").disabled = True

    # canvasapi logs every request and response at INFO; keep only its warnings and errors.
    logging.getLogger("canvasapi").setLevel(logging.WARNING)
