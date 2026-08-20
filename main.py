import argparse
import asyncio

from mcqueen.scripts.scrape import scrape_all_sources
from mcqueen.scrapers.base import ScraperSource
from mcqueen.scrapers.source import SOURCES

from config.logging import setup_logging
from config.settings import JOB_CHANNELS

from db.jobs import upsert_jobs, get_seen_global_ids

from bot.messages import send_job, send_job_batch, BATCH_THRESHOLD
from bot.monday import run_monday


def parse_args() -> argparse.Namespace:
    available_sources = [source.name for source in SOURCES]

    parser = argparse.ArgumentParser(
        description="Scrape configured job sources and publish new postings."
    )
    group = parser.add_mutually_exclusive_group()
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
    return parser.parse_args()


def resolve_sources(source_names: list[str] | None) -> list[ScraperSource]:
    if source_names is None:
        return SOURCES
    return [source for source in SOURCES if source.name in source_names]


async def run(sources: list[ScraperSource]) -> None:
    setup_logging()

    seen_ids: set[str] = set()
    for channel in JOB_CHANNELS.values():
        seen_ids |= get_seen_global_ids(channel.table_name)

    jobs_by_bucket = scrape_all_sources(seen_ids, sources=sources)

    for bucket, jobs in jobs_by_bucket.items():
        if not jobs:
            continue

        channel = JOB_CHANNELS[bucket]
        upsert_jobs(jobs, channel.table_name)

        if channel.telegram_chat_id:
            if len(jobs) > BATCH_THRESHOLD:
                await send_job_batch(
                    jobs, chat_id=channel.telegram_chat_id, is_intern=channel.is_intern
                )
            else:
                for job in jobs:
                    await send_job(
                        job,
                        chat_id=channel.telegram_chat_id,
                        is_intern=channel.is_intern,
                    )


def test_monday() -> None:
    run_monday()


if __name__ == "__main__":
    # args = parse_args()
    # asyncio.run(run(sources=resolve_sources(args.sources)))
    test_monday()
