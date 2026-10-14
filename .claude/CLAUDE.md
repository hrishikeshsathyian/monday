# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Monday is a Telegram assistant for NUS computing students. Python 3.12, managed with `uv`.

## Error handling and logging

Low-level modules catch and log the errors from what they call and return `None`. The caller decides what that failure means and logs the decision.

1. **Catch errors from an external service in the module that calls it, and return `None` on failure.** The caller checks for `None`, decides what happens, and logs that decision with the context it has, such as the user.
   - Example: `integrations/canvas.py` catches `CanvasException` and returns `None`. The runner skips the user's digest if their assignments or classes are `None`.
   - Raise instead only when a caller needs to know *how* the call failed in order to act differently, for example telling the user their key expired rather than retrying tomorrow.
2. **Log where the error is handled, and don't log and then re-raise.** A caller that receives a failure already logged below (`None`) still logs what it does about it, e.g. "Skipping Hermione reminders: could not load authenticated users". Logging the same failure twice is fine when it makes the caller's code readable and the failure traceable.
3. **Low-level modules (`integrations/`, `hermione/nusmods.py`, `db/`) log the error details** (exception type and traceback), since they have them. For example, `nusmods.py` also caches a failed module lookup so it's only requested once per run.
4. **Catch the named exceptions you expect** (`APIError`, `ValidationError`, `CanvasException`) and log them as errors. A function that returns `None` on failure may also catch `Exception`, logged as "Unexpected …", so its caller always gets `None` rather than an exception. Anything that still escapes reaches the top-level catch-all, such as the `gather` handler in `HermioneRunner.run()`.
5. **Give the log line all the context the handler has:** who was affected (chat ID and username), what was attempted, and what happens next (for example "Skipping Hermione digest for chat …").
6. **A fetch function never turns a failure into an empty result.** It returns `None` (or raises) when the lookup fails, and `[]` only when there is genuinely nothing there. A failure is never shown to users as "nothing there": a partial or failed lookup skips the output (e.g. the digest) rather than showing an incomplete one. `get_classes_on` returns `None` if any module's timetable fails, rather than leaving that module out.

## Conventions
- Failure is signalled by returning `None` (see `.claude/CLAUDE.md`); callers check for `None` and log the decision with chat ID and username. Never turn a failed fetch into `[]`.
- Each service keeps its own settings in `<service>/config.py`; only cross-service settings go in `config/settings.py`.
- Entry points call `config.logging.setup_logging()`, which prefixes every line with `[DEV]`/`[PROD]`.
- `README.md` is a portfolio piece, not setup docs: keep it high-level and update it when a service is added or changed.
- Don't hardcode service names in shared bot logic. Which services exist and how they run (toggled, on-demand, needs Canvas) lives in the registries in `bot/config.py` (`MONDAY_TOGGLE_SERVICES`, `ON_DEMAND_SERVICES`, `CANVAS_SERVICES`); check membership there. When services in a group need different behaviour, map service name → handler (e.g. `ON_DEMAND_AFTER_CANVAS_AUTH` in `bot/monday.py`) rather than branching on `service == "..."`. Maps that point at handlers stay next to the handlers, not in `bot/config.py`.
- Every Canvas API call lives in `integrations/canvas.py`; services import the functions they need from there and keep no Canvas code of their own. `integrations/` never imports from a service, so service-specific values (e.g. Hermione's `DIGEST_WINDOW_DAYS`) are passed in as arguments. Functions there serve whichever service calls them and don't call each other's service logic.
- Log messages are f-strings, never `%s` arguments: `logger.error(f"Skipping Hermione digest for chat {chat_id} (@{username}): could not load their classes")`. Write them as a plain sentence saying what happened or was attempted, who it affected (user/chat ID and `@username`), and what happens next. Keep keyword arguments such as `exc_info=True` as they are.
- A service's bot file (`bot/hermione.py`, `bot/walle.py`) gets its data and types only through its own service package (`hermione/`, `walle/`), never from `integrations/` directly. The service package wraps the integration functions it uses with a name that says what they're for in that service and fills in its own settings (e.g. `hermione/assignments.py` `get_digest_assignments`, `walle/courses.py` `get_selectable_courses`). Shared core modules (`db/`, `bot/messages.py`, `bot/text_presets.py`) are fine to import anywhere.
