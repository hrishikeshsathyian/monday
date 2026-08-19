# MondayBot: Canvas Integration Skeleton

## Context

`mcqueen` (job scraping → public Telegram channels) works and is left untouched by this plan. The next step in the README's original vision — a "pull only" personal assistant that unifies Canvas, mail, calendar, etc. into one bot — requires a real architectural departure: mcqueen is a **stateless batch job** triggered hourly by GitHub Actions cron, with zero persistent server and zero per-user state. MondayBot needs an **always-on server** (to receive Telegram webhook updates and serve a Telegram Mini App over HTTPS) and a **per-user data model** (Canvas API tokens, pulled per-user on a schedule), neither of which exist anywhere in this repo today.

Because NUS won't issue a developer API token, each user must generate their own Canvas Personal Access Token and paste it in themselves via a Telegram Mini App (opened from the bot). That token must be stored **reversibly** (decryptable, not hashed) since it's replayed against the Canvas API on the user's behalf.

Given the size of this shift, the goal right now is **not** the full product (daily reminders, timetable, file-sync to Desktop). It's the smallest possible end-to-end skeleton that proves the hard parts work: a user can authenticate via the Mini App, their Canvas token is stored encrypted, and it can be decrypted and used to pull real data back out. Daily reminders, scheduling, and file-sync are explicitly deferred to a later plan once this foundation is proven.

**Decisions already made (with rationale) — do not revisit during implementation:**
- New, separate bot/token for MondayBot (`MONDAYBOT_TOKEN`), distinct from the existing job-channel bot — keeps the anonymous public broadcast persona separate from the personal 1:1 assistant.
- Webhook transport (not polling), one unified FastAPI app serving both the Telegram webhook and the Mini App backend — a public HTTPS endpoint is required for the Mini App anyway, so a second process for polling would be redundant.
- Deployment host is undecided/deferred — build as a standard FastAPI+uvicorn ASGI app, run locally against an ngrok/cloudflared tunnel for now. Nothing should be tied to a specific PaaS's proprietary env.
- Canvas tokens encrypted at rest with app-level symmetric encryption (Fernet, `cryptography` lib), key in an env var separate from the DB.
- Skeleton's "proof it works" deliverable is a **local CLI script**, not a full bot-DM round trip — it takes a `telegram_user_id`, decrypts their stored token, calls Canvas, prints their courses. The bot proactively messaging users with their course list is a later milestone.

---

## Architecture

### New top-level packages (flat, consistent with existing `bot/`, `db/`, `mcqueen/` convention — no `src/` nesting)

```
canvas/
  client.py              CanvasClient — list_courses() w/ pagination via requests
  scripts/
    list_courses.py      CLI: given telegram_user_id, decrypt token, print courses

webapp/
  app.py                 FastAPI() instance, mounts routes + static, GET /health
  telegram_webhook.py    POST /telegram/webhook — verifies secret token, handles /start only
  miniapp_api.py         POST /api/miniapp/canvas-token — verifies initData, stores credential
  telegram_auth.py       verify_init_data(init_data, bot_token) -> user dict | None
  static/
    index.html           Mini App page: loads telegram-web-app.js, paste-token form
    app.js                form submit -> fetch() to miniapp_api

db/
  crypto.py              NEW — Fernet encrypt()/decrypt() helpers
  users.py                NEW — upsert_user(), get_user_by_telegram_id()
  credentials.py           NEW — upsert_credential(), get_credential()
  migrations/
    0001_users_and_service_credentials.sql   NEW — hand-run in Supabase SQL editor
```

**Why `canvas/` and `webapp/` as separate packages, not extending `bot/`:** `bot/` today is a thin, stateless, outbound-only push library (one `Bot` instance + retry-aware `send_message`). It has no concept of receiving updates or a server lifecycle — bolting an ASGI app onto it changes what it structurally is. `webapp/` instead **reuses** `bot/messages.py`'s `send_message` (see config change below) rather than duplicating retry/flood-control logic. `canvas/` is a service-specific API client, structurally parallel to `mcqueen/` — it has no FastAPI/webhook dependency and will later grow independent concerns (slide-file sync), so it shouldn't be coupled to the web server package.

**Why `db/crypto.py` lives under `db/`, not a new `security/` package:** its only caller is `db/credentials.py` — encrypt-before-insert/decrypt-after-select is effectively part of that table's persistence contract. Promote it later if a second, unrelated consumer appears.

### Small, targeted change to existing code: `bot/`

`bot/client.py` currently builds one module-level `Bot` from `TELEGRAM_BOT_TOKEN`. Add a second instance from the new `MONDAYBOT_TOKEN`:
```
bot = Bot(token=TELEGRAM_BOT_TOKEN)          # existing, untouched, used by mcqueen
mondaybot = Bot(token=MONDAYBOT_TOKEN)       # new
```
`bot/messages.py`'s `send_message(chat_id, text, reply_markup=None)` gets one added optional keyword-only param, `bot: Bot = bot` (defaulting to the existing instance so every mcqueen call site is unaffected). `webapp/telegram_webhook.py` calls it explicitly with `bot=mondaybot`. This reuses the existing retry/flood-control logic instead of duplicating it for the new bot.

### `config/settings.py` additions
- `MONDAYBOT_TOKEN = os.environ["MONDAYBOT_TOKEN"]` — required (new bot, from BotFather)
- `CREDENTIAL_ENCRYPTION_KEY = os.environ["CREDENTIAL_ENCRYPTION_KEY"]` — required, Fernet key
- `TELEGRAM_WEBHOOK_SECRET = os.environ["TELEGRAM_WEBHOOK_SECRET"]` — required, checked against Telegram's `X-Telegram-Bot-Api-Secret-Token` header
- `MINI_APP_URL = os.environ["MINI_APP_URL"]` — required; the current public tunnel URL + `/miniapp/` (this will change whenever ngrok restarts — intentionally an env var, not hardcoded)
- `CANVAS_BASE_URL = os.environ.get("CANVAS_BASE_URL", "https://canvas.nus.edu.sg")` — defaulted, not hard-required. **Verify this is actually NUS's Canvas domain before relying on it** — unconfirmed guess, check an actual NUS Canvas login redirect first.

### `pyproject.toml` additions
Add as **direct** dependencies: `fastapi`, `uvicorn[standard]`, `cryptography`. (`cryptography` is currently only a transitive dependency pulled in via `ats-scrapers[scrapers]` → `cloakbrowser` — pin it directly now that `db/crypto.py` imports it, or a future `ats-scrapers` bump could silently break credential decryption.)

---

## Database schema (Supabase/Postgres)

No migration runner exists in this repo (schema is currently hand-managed via the Supabase dashboard). Since this feature introduces two tables at once, start a lightweight, hand-run SQL convention: `db/migrations/0001_users_and_service_credentials.sql`, applied manually via the Supabase SQL editor. Not a real migration framework — just a durable, reviewable record of schema history, which the repo currently has none of. Keep numbering sequentially for future schema changes.

**`users`**

| column | type | constraints |
|---|---|---|
| `id` | `uuid` | PK, `default gen_random_uuid()` |
| `telegram_user_id` | `bigint` | `not null unique` |
| `telegram_chat_id` | `bigint` | `not null` |
| `telegram_username` | `text` | nullable |
| `created_at` | `timestamptz` | `not null default now()` |
| `updated_at` | `timestamptz` | `not null default now()` |

**`service_credentials`** — one generic table, not a Canvas-specific one, since the Mini App's whole point is letting users toggle multiple services later (Canvas now, others eventually) and each needs an identical lifecycle (encrypt/decrypt, one-per-user-per-service, enable/disable).

| column | type | constraints |
|---|---|---|
| `id` | `uuid` | PK, `default gen_random_uuid()` |
| `user_id` | `uuid` | `not null references users(id) on delete cascade` |
| `service` | `text` | `not null check (service in ('canvas'))` — extend as services are added |
| `encrypted_secret` | `text` | `not null` — Fernet output is already URL-safe base64 ASCII |
| `metadata` | `jsonb` | `not null default '{}'::jsonb` — reserves e.g. per-user `base_url` override without a future migration |
| `enabled` | `boolean` | `not null default true` |
| `created_at` / `updated_at` | `timestamptz` | `not null default now()` |
| — | — | `unique (user_id, service)` |

Not splitting into a separate toggle-only `user_services` table for now — every service in scope has a secret to store, so that split would be speculative; it's a clean additive migration later if a secret-less service appears.

---

## Canvas API specifics

- Auth: `Authorization: Bearer <personal_access_token>` header on every request.
- List courses: `GET {CANVAS_BASE_URL}/api/v1/courses?enrollment_state=active&per_page=50` (excludes concluded enrollments; Canvas's page-size default is low, cap is 100).
- Pagination: Canvas returns a GitHub-style `Link` header (`rel="next"`, etc). Use `requests` (already a **direct** dependency, unlike `httpx` which is only transitive here) — `response.links.get("next", {}).get("url")` parses this for free. Loop until `"next"` is absent.
- Base URL: hardcoded default via `CANVAS_BASE_URL`, but `service_credentials.metadata` already reserves a `base_url` key for later per-user/multi-institution override without a schema change.

---

## Telegram Mini App `initData` verification (`webapp/telegram_auth.py`)

`verify_init_data(init_data: str, bot_token: str) -> dict | None`:

1. Parse `init_data` as a URL-encoded query string.
2. Extract and remove `hash` (not part of the signed content).
3. Build the data-check-string: remaining `key=value` pairs, sorted alphabetically by key, joined with `\n`.
4. `secret_key = HMAC_SHA256(key=b"WebAppData", msg=bot_token.encode()).digest()` — note the token is the *message*, `"WebAppData"` is the *key* (easy to get backwards).
5. `computed_hash = HMAC_SHA256(key=secret_key, msg=data_check_string.encode()).hexdigest()`.
6. Compare to the received `hash` with `hmac.compare_digest` — never `==` (timing side-channel).
7. Reject if `auth_date` is older than ~5 minutes — this is a one-shot "submit right after opening" action, not a long session, so a tight window is appropriate.
8. On success, parse the `user` field (URL-decoded JSON) for the trusted `telegram_user_id` — this, not anything else client-supplied, is the identity used to save the credential.

---

## Webhook + `/start` behavior (`webapp/telegram_webhook.py`)

Skip `telegram.ext.Application`/`CommandHandler` for this skeleton — this repo has never used it, and wiring its lifecycle into FastAPI's is real complexity to handle exactly one command. Parse the raw webhook JSON directly and reuse `bot.messages.send_message` (see config change above).

`POST /telegram/webhook`:
1. Verify `X-Telegram-Bot-Api-Secret-Token` header against `TELEGRAM_WEBHOOK_SECRET`; 401 if missing/mismatched.
2. Defensively `.get()`-chain the body — never trust exact shape of untrusted input.
3. If message text doesn't start with `/start`, return `{"ok": true}` and do nothing else.
4. Else extract `telegram_user_id`, `telegram_chat_id`, `username` from `message.from`/`message.chat`.
5. `db.users.upsert_user(...)`.
6. Reply via `send_message(..., bot=mondaybot, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Open Setup", web_app=WebAppInfo(url=MINI_APP_URL))]]))`.
7. Return `{"ok": true}` — no course list sent from here; that's a later milestone.

---

## Ordered build sequence

Each step is independently, manually verifiable before moving to the next.

1. **Deps + env**: add `fastapi`, `uvicorn[standard]`, `cryptography` to `pyproject.toml`, `uv sync`. Add new required env vars to `.env`. Register the new bot with BotFather, get `MONDAYBOT_TOKEN`.
2. **Schema**: hand-run `0001_users_and_service_credentials.sql` in Supabase SQL editor. Verify via the Supabase table editor.
3. **Encryption in isolation**: build `db/crypto.py`. Verify in a throwaway REPL — round-trip a fake string, confirm a tampered ciphertext raises `InvalidToken`. No DB/network yet.
4. **DB access against real tables**: build `db/users.py`, `db/credentials.py`. Verify via REPL against real Supabase — upsert a fake user + credential, fetch, decrypt, confirm round trip.
5. **Canvas client in isolation**: build `canvas/client.py`. Verify standalone with your own real Canvas PAT in a throwaway env var — confirms auth header/base URL/endpoint before anything else sits on top.
6. **CLI script — core proof-of-concept**: build `canvas/scripts/list_courses.py` wiring 3–5 together. Manually seed one real `users` row + one real encrypted `service_credentials` row via a one-off REPL insert, run `uv run python -m canvas.scripts.list_courses <telegram_user_id>`, confirm it prints your real course list. **This is the deliverable called out as the skeleton's goal.**
7. **FastAPI skeleton, no Telegram logic**: build `webapp/app.py` with `GET /health`. Run via `uv run uvicorn webapp.app:app --reload --port 8000`. Start an ngrok/cloudflared tunnel, confirm `/health` reachable through it — isolates tunnel plumbing before Telegram-specific complexity.
8. **Webhook route**: build `webapp/telegram_webhook.py`. Register via a one-off `setWebhook` call (curl) with the tunnel URL + `secret_token`. Send `/start` from Telegram, confirm: request lands in FastAPI logs, `users` row appears/updates, reply arrives in Telegram (inline button can 404 for now — Mini App isn't live yet).
9. **`initData` verification in isolation**: build `webapp/telegram_auth.py`. Verify against a real captured `initData` string (e.g. log `Telegram.WebApp.initData` from a minimal test page) before trusting it in a route.
10. **Mini App + credential-save route**: build `webapp/static/index.html`/`app.js` + `webapp/miniapp_api.py`. Open the Mini App via the real `/start` reply's inline button (must be opened from inside actual Telegram, not a desktop browser tab, or `initData` will be empty). Paste a real Canvas PAT, submit, confirm a correctly-encrypted row lands in `service_credentials`.
11. **Closed-loop verification**: re-run the milestone-6 CLI script, now reading the credential captured via the real Mini App flow (not the manually-seeded one). Confirms the full chain: `/start` → Mini App → paste token → CLI reads DB → calls Canvas → prints courses.

---

## Risks / gotchas to keep in mind while building

- **Webhook endpoint is public** — the secret-token check is not optional; anyone who finds the tunnel URL can POST to it otherwise.
- **ngrok free-tier URLs change on every restart** — `setWebhook` must be re-run each time or Telegram silently queues/drops updates. `getWebhookInfo` is the fastest way to debug "nothing arrives." A named/static tunnel removes this friction.
- **`initData` only works inside the real Telegram client** — testing the Mini App in a plain desktop browser tab won't produce valid `initData`; must launch via the bot's inline `web_app` button.
- **One symmetric key decrypts every user's credential** — losing/rotating `CREDENTIAL_ENCRYPTION_KEY` without a re-encryption plan makes all stored tokens permanently unreadable. Keep it out of version control, back it up separately from `.env`.
- **`db/client.py` hard-fails at import if Supabase env vars are unset** — the FastAPI process needs its own copy of those env vars, not just the GitHub Actions cron job's.
- **Canvas rate limits are per-token, cost-based** (`X-Rate-Limit-Remaining` header) — irrelevant for one call in the skeleton, but flag in `canvas/client.py`: a later multi-user daily job must NOT fan out concurrently across users' personal tokens the way mcqueen fans out over public ATS APIs — each token belongs to a real individual.
- This skeleton is fully additive — the GitHub Actions cron pipeline (`main.py --all`) and the new FastAPI server are separate runtime lifecycles sharing only `config/settings.py` and `db/client.py`. No risk to the existing mcqueen pipeline.

---

## Explicitly out of scope for this skeleton (future plans)

- Daily reminder scheduling (quizzes, timetable/assignments due)
- Lecture slide file-sync to Desktop
- Mini App service-selection UI for services beyond Canvas
- Bot proactively DMing users (beyond the one `/start` welcome reply)
- Any real deployment target (VPS/PaaS) — local + tunnel only for now

---

## Verification

- Milestone 6 (CLI prints real courses using a manually-seeded credential) is the primary correctness check requested by the user.
- Milestone 11 (same CLI, now fed by a credential captured through the real `/start` → Mini App → paste-token flow) proves the full pipeline end-to-end.
- No automated test suite exists in this repo today; verification here is manual/REPL-driven at each milestone, consistent with how mcqueen itself has been verified (no test suite there either).
