import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config.settings import MONDAY_BOT_TOKEN
from bot.hermione import (
    AWAITING_CANVAS_API_KEY,
    cancel_hermione_auth,
    prompt_canvas_auth,
    receive_canvas_api_key,
)
from db.service_credentials import (
    get_service_credentials,
    set_service_enabled,
)
from db.models import DbUserService
from db.users import get_user, try_create_user

logger = logging.getLogger(__name__)


# Services exposed as Telegram commands.
# The key is the command name, e.g. /mcqueen or /hermione.
MONDAY_SERVICES: dict[str, str] = {
    "mcqueen": "Lightning Fast Live Scraper for SG Computing Internships",
    "hermione": "Automatic Canvas File Sync & Quiz Deadline Reminder",
}


ALREADY_REGISTERED_TEXT = (
    "<b>You're already set up!</b>\n\n"
    "You can manage your services anytime using the commands below."
)

WELCOME_TEXT = (
    "👋 <b>Welcome to Monday!</b>\n\n"
    "You're all set.\n\n"
    "Connect the services you'd like Monday to use. "
    "You can turn them on or off at any time."
)

SIGNUP_FAILED_TEXT = (
    "⚠️ <b>Couldn't complete registration</b>\n\n"
    "Something went wrong while setting up your account.\n"
    "Please try again in a moment."
)

NOT_REGISTERED_TEXT = (
    "<b>Oops! You're not registered yet.</b>\n\n"
    "Run /start first to get set up."
)

SERVICE_STATE_FAILED_TEXT = (
    "⚠️ <b>Couldn't load your services</b>\n\n"
    "Please try again in a moment."
)


def format_service_overview(
    service_credentials: list[DbUserService],
) -> str:
    """Build the Telegram message showing each service's current state."""

    lines = [
        "⚙️ <b>Your services</b>",
        "",
    ]

    for credential in service_credentials:
        service_name = credential.service.title()

        if credential.enabled:
            lines.append(
                f"✅ <b>{service_name}</b>\n"
                f"   Enabled · /{credential.service}"
            )
        else:
            lines.append(
                f"○ <b>{service_name}</b>\n"
                f"   Disabled · /{credential.service}"
            )

        lines.append("")

    lines.append("Use a command above to toggle a service.")

    return "\n".join(lines)


async def send_service_overview(update: Update) -> None:
    """Fetch the user's services and send their current enabled/disabled states."""

    # Some Telegram updates do not contain a normal message.
    if update.message is None:
        return

    user = update.effective_user
    if user is None:
        return

    service_credentials = get_service_credentials(user.id)

    if service_credentials is None:
        await update.message.reply_text(
            SERVICE_STATE_FAILED_TEXT,
            parse_mode="HTML",
        )
        return

    await update.message.reply_text(
        format_service_overview(service_credentials),
        parse_mode="HTML",
    )


async def handle_register(
    update: Update,
    _context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /start and create the user's Monday account if needed."""

    if update.message is None:
        return

    user = update.effective_user
    chat = update.effective_chat

    if user is None or chat is None:
        logger.error(
            "/start triggered without effective user or chat. "
            "Effective user: %s, Effective chat: %s",
            user,
            chat,
        )
        return

    # Existing users do not need to be registered again.
    if get_user(user.id) is not None:
        logger.info(
            "User %s (@%s) is already registered",
            user.id,
            user.username,
        )

        await update.message.reply_text(
            ALREADY_REGISTERED_TEXT,
            parse_mode="HTML",
        )

        await send_service_overview(update)
        return

    logger.info(
        "Onboarding new user %s (@%s)...",
        user.id,
        user.username,
    )

    # Store the Telegram user/chat details and initialise their services.
    if not try_create_user(
        telegram_user_id=user.id,
        telegram_chat_id=chat.id,
        telegram_username=user.username,
    ):
        await update.message.reply_text(
            SIGNUP_FAILED_TEXT,
            parse_mode="HTML",
        )
        return

    await update.message.reply_text(
        WELCOME_TEXT,
        parse_mode="HTML",
    )

    await send_service_overview(update)


async def handle_service_toggle(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Toggle the service corresponding to the command the user sent."""

    del context

    if update.message is None:
        return ConversationHandler.END

    user = update.effective_user

    if user is None:
        await update.message.reply_text(
                    SERVICE_STATE_FAILED_TEXT,
                    parse_mode="HTML",
        )
        return ConversationHandler.END

    # Extract "hermione" from commands such as:
    # /hermione
    # /hermione@MondayBot
    command = (
        (update.message.text or "")
        .split()[0]
        .lstrip("/")
        .split("@")[0]
    )

    service = command

    # Service commands are only available after /start registration.
    if get_user(user.id) is None:
        await update.message.reply_text(
            NOT_REGISTERED_TEXT,
            parse_mode="HTML",
        )
        return ConversationHandler.END

    service_credentials = get_service_credentials(user.id)

    if service_credentials is None:
        await update.message.reply_text(
            SERVICE_STATE_FAILED_TEXT,
            parse_mode="HTML",
        )
        return ConversationHandler.END

    # Find the current enabled state for the requested service.
    current_state = next(
        (
            credential.enabled
            for credential in service_credentials
            if credential.service == service
        ),
        None,
    )

    if current_state is None:
        await update.message.reply_text(
            SERVICE_STATE_FAILED_TEXT,
            parse_mode="HTML",
        )
        return ConversationHandler.END

    new_state = not current_state

    # Hermione requires a Canvas API key before it can be enabled.
    # If the user has not authenticated before, begin the auth conversation
    # instead of enabling the service immediately.
    if (
        service == "hermione"
        and new_state
        and not next(
            credential.encrypted_secret
            for credential in service_credentials
            if credential.service == service
        )
    ):
        await prompt_canvas_auth(update)

        # ConversationHandler will now route the user's next text message
        # to receive_canvas_api_key().
        return AWAITING_CANVAS_API_KEY

    # Services that do not require authentication can be toggled immediately.
    if not set_service_enabled(
        user.id,
        service,
        new_state,
    ):
        await update.message.reply_text(
            SERVICE_STATE_FAILED_TEXT,
            parse_mode="HTML",
        )
        return ConversationHandler.END

    if new_state:
        await update.message.reply_text(
            f"<b>{service.title()}</b> enabled.",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            f"<b>{service.title()}</b> disabled.",
            parse_mode="HTML",
        )

    await send_service_overview(update)

    # No further interaction is needed for this command.
    return ConversationHandler.END


def run_monday() -> None:
    """Create the Telegram application, register handlers and start polling."""

    app = (
        Application.builder()
        .token(MONDAY_BOT_TOKEN)
        .build()
    )

    # /start handles initial user registration.
    app.add_handler(
        CommandHandler(
            "start",
            handle_register,
        )
    )

    # Service commands act as both normal toggles and entry points into
    # multi-step flows such as Hermione's Canvas authentication.
    app.add_handler(
        ConversationHandler(
            entry_points=[
                CommandHandler(
                    list(MONDAY_SERVICES.keys()),
                    handle_service_toggle,
                ),
            ],

            # If handle_service_toggle returns AWAITING_CANVAS_API_KEY,
            # the next non-command text message is treated as the API key.
            states={
                AWAITING_CANVAS_API_KEY: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        receive_canvas_api_key,
                    ),
                ],
            },

            # /cancel lets the user exit the Hermione authentication flow.
            fallbacks=[
                CommandHandler(
                    "cancel",
                    cancel_hermione_auth,
                ),
            ],
        )
    )

    logger.info("MondayBot polling for updates")

    # run_polling manages its own event loop,
    # so don't call this from inside asyncio.run().
    app.run_polling()
