import argparse
import asyncio

from mcqueen.runner import McQueenRunner
from mcqueen.scrapers.source import SOURCES

from config.logging import setup_logging

from bot.monday import run_monday


def parse_args() -> argparse.Namespace:
    available_sources = [source.name for source in SOURCES]

    parser = argparse.ArgumentParser(
        description="Monday — job scraping and assistant bot."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scrape = subparsers.add_parser(
        "scrape",
        help="Scrape configured job sources and publish new postings.",
    )
    group = scrape.add_mutually_exclusive_group()
    group.add_argument(
        "--all",
        action="store_true",
        help="Scrape every configured source (default).",
    )
    group.add_argument(
        "--sources",
        nargs="+",
        choices=available_sources,
        metavar="SOURCE",
        help=f"Scrape only these sources. Choices: {', '.join(available_sources)}",
    )

    subparsers.add_parser("monday", help="Run the MondayBot polling loop.")

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    setup_logging()

    if args.command == "monday":
        # run_polling manages its own event loop, so never wrap this in asyncio.run().
        run_monday()
    else:
        asyncio.run(McQueenRunner.from_source_names(args.sources).run())
