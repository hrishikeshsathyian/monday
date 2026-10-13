"""User-facing message text sent by the Monday bot, grouped by the module that sends it."""

# ---------------------------------------------------------------------------
# bot/monday.py: registration, /status and service toggles
# ---------------------------------------------------------------------------

ALREADY_REGISTERED_TEXT = (
    "<b>You're already registered with Monday!</b>\n\n"
    "You can manage your services anytime using the commands below."
)

WELCOME_TEXT = "👋 <b>Welcome to Monday!</b>\n\n" "You're all set.\n\n"

SIGNUP_FAILED_TEXT = (
    "😔 <b>Couldn't complete registration, something went wrong while setting up your account.</b>\n\n"
    "Please try again in a moment, or contact support if it persists."
)

NOT_REGISTERED_TEXT = (
    "<b> ⚠️ Oops! You're not registered yet.</b>\n\n" "Run /start first to get set up."
)

SERVICE_STATE_FAILED_TEXT = (
    "⚠️ <b>Oops! An error occured and we could not load your services</b>\n\n"
)

# Sent after a toggle so users know what to expect from the service.
SERVICE_ENABLED_TEXT: dict[str, str] = {
    "mcqueen": (
        "<b>McQueen enabled.</b> New internship listings will be sent to you live as they come in ⚡"
    ),
    "hermione": (
        "<b>Hermione enabled.</b> Your next daily digest will arrive tomorrow morning 📚"
    ),
}

SERVICE_DISABLED_TEXT: dict[str, str] = {
    "mcqueen": "<b>McQueen disabled.</b> You won't receive internship listings anymore.",
    "hermione": "<b>Hermione disabled.</b> You won't receive daily digests anymore.",
}


# ---------------------------------------------------------------------------
# bot/canvas_auth.py: connecting a Canvas account
# ---------------------------------------------------------------------------

CANVAS_AUTH_PROMPT_TEXT = (
    "🔐 <b>Connect Monday to Canvas</b>\n\n"
    "Paste your Canvas API key to continue. Monday's Canvas services all share this key.\n\n"
    "<b>Where to find it? </b> \n Canvas → Account → Settings → Approved Integrations → New Access Token\n\n"
    "Your token is encrypted safely before being stored and is never exposed in plaintext.\n\n"
    "Use /cancel to cancel authentication flow."
)
CANVAS_CHECKING_KEY_TEXT = "Validating your Canvas API key…"
CANVAS_INVALID_KEY_TEXT = (
    "⚠️ <b>That Canvas API key didn't work.</b>\n\n"
    "Please try again with another key, or use /cancel to stop the authentication process."
)
CANVAS_KEY_CHECK_UNAVAILABLE_TEXT = (
    "⚠️ <b>Couldn't reach Canvas to check your key.</b>\n\n"
    "Please send it again in a moment, or use /cancel to stop the authentication process."
)
CANVAS_KEY_SAVE_FAILED_TEXT = (
    "⚠️ <b>Your Canvas Key was valid but we couldn't save it</b>\n\n"
    "Please try again in a moment."
)
CANVAS_CONNECTED_TEXT = (
    "✅ <b>Canvas connected.</b> Your Canvas key will be valid for the next 3 months."
)
CANVAS_AUTH_CANCELLED_TEXT = "Canvas authentication flow cancelled."


# ---------------------------------------------------------------------------
# bot/walle.py: Wall-E course picker
# ---------------------------------------------------------------------------

WALLE_PICKER_TEXT = (
    "🤖📦 <b>[Wall-E] Course Files</b>\n\n"
    "Pick a course and I'll bring you all of its Canvas files in one zip."
)
WALLE_NO_COURSES_TEXT = (
    "🤖📦 <b>[Wall-E]</b> You have no active Canvas courses right now."
)
WALLE_KEY_LOAD_FAILED_TEXT = (
    "⚠️ <b>Couldn't load your Canvas key</b>\n\n" "Please try /walle again in a moment."
)
WALLE_CANVAS_UNAVAILABLE_TEXT = (
    "⚠️ <b>Couldn't reach Canvas to load your courses</b>\n\n"
    "Please try /walle again in a moment."
)
WALLE_KEY_REJECTED_TEXT = (
    "⚠️ <b>Canvas no longer accepts your saved key</b>\n\n"
    "It may have expired or been revoked. Please try again."
)
