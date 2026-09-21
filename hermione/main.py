import logging
import asyncio

from canvasapi import Canvas
from canvasapi.exceptions import CanvasException

from config.logging import setup_logging

from .runner import HermioneRunner

CANVAS_URL = "https://canvas.nus.edu.sg"

logger = logging.getLogger(__name__)


def canvas_healthcheck(api_key: str) -> bool:
    try:
        canvas = Canvas(CANVAS_URL, api_key)

        canvas.get_current_user()

        return True

    except CanvasException:
        logger.warning("Canvas healthcheck rejected an API key")
        return False

    except Exception:
        logger.exception("Unexpected Canvas healthcheck failure")
        return False


def main() -> None:
    """Configure the process and run one Hermione cycle."""

    setup_logging()
    asyncio.run(HermioneRunner().run())


if __name__ == "__main__":
    main()
