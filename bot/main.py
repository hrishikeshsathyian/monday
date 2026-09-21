"""Executable entry point for the Monday Telegram bot."""

from config.logging import setup_logging

from .monday import run_monday


def main() -> None:
    """Configure the process and start Telegram polling."""

    setup_logging()
    # run_polling manages its own event loop.
    run_monday()


if __name__ == "__main__":
    main()
