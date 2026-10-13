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
from bot.canvas_auth import (
    AWAITING_CANVAS_API_KEY,
    CanvasAuthResult,
    cancel_canvas_auth,
    prompt_canvas_auth,
    receive_canvas_api_key,
)
from db.service_credentials import (
    get_service_credentials,
    set_service_enabled,
)
from db.user_credentials import has_credential
from db.models import DbUserService
from db.users import get_user, try_create_user

logger = logging.getLogger(__name__)


# Services exposed as Telegram commands.
MONDAY_SERVICES: dict[str, str] = {
    "mcqueen": "Live Alerts for new SG Computing Internship Listings",
    "hermione": "Automatic Daily NUS Canvas Digest: Upcoming Classes and Deadlines",
}

# Services that need the user's Canvas key before they can be enabled.
CANVAS_SERVICES = {"hermione"}

# user_data key remembering which service started the Canvas auth flow.
PENDING_CANVAS_SERVICE = "pending_canvas_service"


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
    "😔 <b>Couldn't complete registration</b>\n\n"
    "Something went wrong while setting up your account.\n"
    "Please try again in a moment."
)

NOT_REGISTERED_TEXT = (
    "<b>Oops! You're not registered yet.</b>\n\n" "Run /start first to get set up."
)

SERVICE_STATE_FAILED_TEXT = (
    "⚠️ <b>Couldn't load your services</b>\n\n" "Please try again in a moment."
)

# Sent after a toggle so users know what to expect from the service.
SERVICE_ENABLED_TEXT: dict[str, str] = {
    "mcqueen": (
        "<b>McQueen enabled.</b> New internship listings will be sent to you live as they come in."
    ),
    "hermione": (
        "<b>Hermione enabled.</b> Your next daily digest will arrive tomorrow morning!"
    ),
}

SERVICE_DISABLED_TEXT: dict[str, str] = {
    "mcqueen": "<b>McQueen disabled.</b> You won't receive internship listings anymore.",
    "hermione": "<b>Hermione disabled.</b> You won't receive daily digests anymore.",
}


def format_service_overview(
    service_credentials: list[DbUserService],
) -> str:

    lines = [
        "⚙️ <b>Your services</b>",
        "",
    ]

    for credential in service_credentials:
        service_name = credential.service.title()
        description = MONDAY_SERVICES.get(credential.service, "")
        icon, state = ("✅", "Enabled") if credential.enabled else ("○", "Disabled")

        lines.append(
            f"{icon} <b>{service_name}</b> - {description}\n"
            f"   {state} · /{credential.service}"
        )

        lines.append("")

    lines.append("Press the commands above to toggle a service on and off.")

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


async def handle_status(
    update: Update,
    _context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /status by sending the user their service overview."""

    if update.message is None or update.effective_user is None:
        return

    if get_user(update.effective_user.id) is None:
        await update.message.reply_text(
            NOT_REGISTERED_TEXT,
            parse_mode="HTML",
        )
        return

    await send_service_overview(update)


async def handle_service_toggle(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Toggle the service corresponding to the command the user sent."""

    if update.message is None:
        return ConversationHandler.END

    user = update.effective_user

    if user is None:
        await update.message.reply_text(
            SERVICE_STATE_FAILED_TEXT,
            parse_mode="HTML",
        )
        return ConversationHandler.END

    command = (update.message.text or "").split()[0].lstrip("/").split("@")[0]

    service = command

    # Check is user is already registered
    is_user_registered = True if get_user(user.id) else False
    if not is_user_registered:
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
        if not service_credentials:
            logger.error(
                "User %s has no service credential rows (requested %s)",
                user.id,
                service,
            )
        else:
            logger.error(
                "User %s has no credential row for service %s (found: %s)",
                user.id,
                service,
                [credential.service for credential in service_credentials],
            )
        await update.message.reply_text(
            SERVICE_STATE_FAILED_TEXT,
            parse_mode="HTML",
        )
        return ConversationHandler.END

    new_state = not current_state

    # Canvas services need the user's Canvas key before they can be enabled.
    # If the user has not connected Canvas yet, begin the auth conversation
    # instead of enabling the service immediately.
    if service in CANVAS_SERVICES and new_state:
        has_canvas_key = has_credential(user.id, "canvas")
        if has_canvas_key is None:
            logger.error(
                "Not enabling %s for user %s (@%s): could not check their Canvas key",
                service,
                user.id,
                user.username,
            )
            await update.message.reply_text(
                SERVICE_STATE_FAILED_TEXT,
                parse_mode="HTML",
            )
            return ConversationHandler.END

        if not has_canvas_key:
            if context.user_data is not None:
                context.user_data[PENDING_CANVAS_SERVICE] = service
            await prompt_canvas_auth(update)

            # ConversationHandler will now route the user's next text message
            # to handle_canvas_api_key().
            return AWAITING_CANVAS_API_KEY

    if await set_service_and_reply(update, user.id, service, new_state):
        await send_service_overview(update)

    # No further interaction is needed for this command.
    return ConversationHandler.END


async def set_service_and_reply(
    update: Update,
    telegram_user_id: int,
    service: str,
    enabled: bool,
) -> bool:
    """Enable or disable a service and tell the user what to expect."""

    if update.message is None:
        return False

    if not set_service_enabled(telegram_user_id, service, enabled):
        await update.message.reply_text(
            SERVICE_STATE_FAILED_TEXT,
            parse_mode="HTML",
        )
        return False

    await update.message.reply_text(
        SERVICE_ENABLED_TEXT[service] if enabled else SERVICE_DISABLED_TEXT[service],
        parse_mode="HTML",
    )
    return True


async def handle_canvas_api_key(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Run the Canvas key check, then enable the service that asked for it."""

    result = await receive_canvas_api_key(update)
    if result is CanvasAuthResult.RETRY:
        return AWAITING_CANVAS_API_KEY

    service = (
        context.user_data.pop(PENDING_CANVAS_SERVICE, None)
        if context.user_data is not None
        else None
    )

    if result is CanvasAuthResult.CONNECTED and update.effective_user is not None:
        if service is None:
            logger.error(
                "Canvas connected for user %s (@%s) but no service was waiting on it",
                update.effective_user.id,
                update.effective_user.username,
            )
        else:
            await set_service_and_reply(update, update.effective_user.id, service, True)

    await send_service_overview(update)
    return ConversationHandler.END


def run_monday() -> None:
    """Create the Telegram application, register handlers and start polling."""

    app = Application.builder().token(MONDAY_BOT_TOKEN).build()

    # /start handles initial user registration.
    app.add_handler(
        CommandHandler(
            "start",
            handle_register,
        )
    )

    # /status shows the user which services they have enabled.
    app.add_handler(
        CommandHandler(
            "status",
            handle_status,
        )
    )

    # Service commands act as both normal toggles and entry points into
    # multi-step flows such as Canvas authentication.
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
                        handle_canvas_api_key,
                    ),
                ],
            },
            # /cancel lets the user exit the Canvas authentication flow.
            fallbacks=[
                CommandHandler(
                    "cancel",
                    cancel_canvas_auth,
                ),
            ],
        )
    )

    logger.info("MondayBot polling for updates")

    # run_polling manages its own event loop,
    # so don't call this from inside asyncio.run().
    app.run_polling()
