"""Compatibility launcher for the Monday Telegram bot.

Run package-local entry points with ``uv run -m bot.main``,
``uv run -m mcqueen.main``, or ``uv run -m hermione.main``.
"""

from bot.main import main

if __name__ == "__main__":
    main()
