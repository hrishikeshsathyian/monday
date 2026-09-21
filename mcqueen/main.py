"""Executable entry point for the McQueen job-scraping service."""

import argparse
import asyncio

from config.logging import setup_logging

from .runner import McQueenRunner
from .scrapers.source import SOURCES


def parse_args() -> argparse.Namespace:
    """Parse source-selection options for a McQueen run."""

    available_sources = [source.name for source in SOURCES]
    parser = argparse.ArgumentParser(
        description="McQueen — scrape job sources and publish new postings."
    )
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
    """Configure the process and run the McQueen pipeline once."""

    args = parse_args()
    setup_logging()
    asyncio.run(McQueenRunner.from_source_names(args.sources).run())


if __name__ == "__main__":
    main()
