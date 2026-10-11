# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Python 3.12, managed with `uv`. Run everything from the repo root (entry points are run with `-m`).

```bash
uv sync                          # install deps into .venv
uv run -m mcqueen.main --all     # run one McQueen scrape + publish cycle (all sources)
uv run -m mcqueen.main --sources tiktok apple   # limit to named sources
uv run -m bot.main               # start the Monday Telegram bot (long-polling, runs until killed)
uv run -m hermione.main          # run one Hermione pass (sends course overviews to enabled users)
uv run black .                   # format (black is the only formatter installed)
```

There is no test suite and no lint config (no pytest, ruff, or mypy setup). Don't look for a "run a single test" command; there isn't one. `.vscode/settings.json` sets Pylance to `standard` type checking.

Required environment variables (loaded from `.env` by `config/settings.py`; the app crashes at import if any are missing):
`SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_CHAT_ID_NON_INTERN`, `MONDAY_BOT_TOKEN`, `FERNET_KEY`.

## Architecture

Three services share one Supabase database and two Telegram bots. The README and `docs/architecture.png` give the high-level picture; the notes below cover what isn't obvious from reading one file.

**McQueen (job scraper, broadcast-only).** `.github/workflows/scrape.yml` runs `mcqueen.main --all` hourly. The pipeline lives in `mcqueen/runner.py` (`McQueenRunner.run`):
1. Load every `global_id` already stored across all three job tables, so the set of "seen" jobs is global, not per channel.
2. Scrape each `ScraperSource` (`mcqueen/scrapers/source.py`) in a thread pool. Scraping itself comes from the external `ats_scrapers` package; this repo supplies the company slugs (`mcqueen/data/*.csv`) and the filters.
3. Classify each job into one of three buckets: tech intern, tech non-intern, non-tech. Classification is regex-based in `mcqueen/scrapers/filters.py`. Non-Singapore and already-seen jobs are dropped first; non-tech is checked before intern.
4. Upsert into Supabase **before** publishing to Telegram. A failed send therefore still marks the job as seen and it will not be re-sent. This is deliberate.
5. Publish via `bot/mcqueen.py` to the Telegram channel (the temporary backwards-compatible path described under Two bots). Batches over `BATCH_THRESHOLD` (10) are sent as grouped messages. `non_tech` has no Telegram channel: it is stored but never broadcast.

The bucket keys (`tech_intern`, `tech_non_intern`, `non_tech`) are string-matched between `mcqueen/runner.py` and the `JOB_CHANNELS` dict in `config/settings.py`. Changing one without the other breaks publishing.

**Monday (user-facing Telegram bot).** `bot/monday.py` runs `Application.run_polling()` with `MONDAY_BOT_TOKEN`. `/start` registers a user, and `/mcqueen` and `/hermione` toggle per-user services. Toggling Hermione on without a stored key starts a `ConversationHandler` flow (`bot/hermione.py`) that validates a Canvas API key against Canvas, encrypts it, and stores it.

**Hermione (Canvas digest).** `hermione/runner.py` loads every enabled Hermione credential, decrypts the key, fetches active courses through `hermione/canvas.py`, and messages each user privately through the Monday bot. Nothing in the repo schedules this; no workflow references it, so it is run by hand or from somewhere outside the repo.

**Two bots (temporary).** `bot/client.py` builds a `bot` (broadcast, `TELEGRAM_BOT_TOKEN`) and a `mondaybot` (user-facing, `MONDAY_BOT_TOKEN`). The broadcast bot exists only to keep the McQueen Telegram channels running for backwards compatibility. The planned end state is a single Monday bot that handles McQueen alerts as 1-1 messages to each user, at which point the broadcast bot and the channel `TELEGRAM_CHAT_ID*` path go away. Until then:
- `bot/messages.py` defaults to the broadcast bot, so Hermione passes `bot=mondaybot` explicitly. Forgetting that argument sends the message from the wrong bot.
- Don't add new user-facing features on the broadcast bot. New per-user behaviour belongs on `mondaybot`, and it should be written so McQueen can later call the same per-user path instead of the channel path.

**Secrets.** Canvas keys are Fernet-encrypted with `FERNET_KEY` (`security/credentials.py`) and never logged. Rotating `FERNET_KEY` makes every stored key undecryptable.

**Persistence conventions.** `db/` functions do not raise on database errors. They log and return `False`, `None`, or an empty set, and callers check the result. Follow this pattern in new DB code rather than adding try/except at call sites.

## Gotchas

- **Import-time side effects.** `config/settings.py` reads env vars and calls `load_dotenv()` at import. `bot/client.py` constructs `Bot` objects at import. `db/client.py` reads `os.environ` directly and does *not* call `load_dotenv`, so it only works because `config.settings` is imported first. Keep that order in mind when adding new entry points.
- **Telegram messages use HTML parse mode.** Escape any scraped or user-supplied text with `html.escape()`, as the existing senders do.
- **Expiry is written but not enforced.** `set_service_secret` sets `expires_at` three months out, but `get_enabled_hermione_credentials` and `HermioneRunner` never filter on it. Expired keys keep being used until Canvas rejects them.
- **Senior roles are dropped silently.** In `ScraperSource._filter`, senior non-intern postings are discarded; the logging that would report them is commented out.
- **`mcqueen/data/*.csv.bak`** are not read by anything; `source.py` only loads the plain `.csv` names.
- **Root `main.py`** is a compatibility launcher that just calls `bot.main`. Use the `-m` forms above for the other services.
