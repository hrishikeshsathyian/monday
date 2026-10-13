"""Executable entry point for the McQueen job-scraping service."""

import argparse
import asyncio

from config.logging import setup_logging

from .runner import McQueenRunner
from .scrapers.source import SOURCES


def parse_args() -> argparse.Namespace:
    available_sources = [source.name for source in SOURCES]
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--all",
        action="store_true",
        help="Scrape every configured source (the default).",
    )
    group.add_argument(
        "--sources",
        nargs="+",
        choices=available_sources,
        metavar="SOURCE",
        help=f"Scrape only these sources. Choices: {', '.join(available_sources)}",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging()
    # default to all if nothing selected via "--sources" command line flag
    source_names = args.sources or [source.name for source in SOURCES]
    asyncio.run(McQueenRunner.from_source_names(source_names).run())


if __name__ == "__main__":
    main()
