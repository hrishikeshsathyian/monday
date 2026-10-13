import logging

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config.settings import MONDAY_BOT_TOKEN
from bot.config import (
    CANVAS_DEPENDENT_SERVICES,
    MONDAY_TOGGLE_SERVICES,
    MONDAY_LONG_RUNNING_SERVICES,
)
from bot.text_presets import (
    ALREADY_REGISTERED_TEXT,
    NOT_REGISTERED_TEXT,
    SERVICE_DISABLED_TEXT,
    SERVICE_ENABLED_TEXT,
    SERVICE_STATE_FAILED_TEXT,
    SIGNUP_FAILED_TEXT,
    WELCOME_TEXT,
)
from bot.canvas_auth import (
    AWAITING_CANVAS_API_KEY,
    CanvasAuthResult,
    cancel_canvas_auth,
    pop_pending_service,
    prompt_canvas_auth,
    receive_canvas_api_key,
)
from bot.walle import (
    COURSE_CALLBACK_PATTERN,
    CoursePickerResult,
    handle_course_selected,
    send_course_picker,
)
from db.user_services import (
    get_user_services,
    set_service_enabled,
)
from db.user_credentials import has_credential
from db.models import DbUserService
from db.users import get_user, try_create_user

logger = logging.getLogger(__name__)

# What each on-demand service (see ON_DEMAND_SERVICES) does once Canvas is
# connected for it. Lives here rather than bot/config.py because it points at handlers.
ON_DEMAND_AFTER_CANVAS_AUTH = {
    "walle": send_course_picker,
}


def format_service_overview(
    user_services: list[DbUserService],
) -> str:

    lines = [
        "⚙️ <b>Your services</b>",
        "",
    ]

    for user_service in user_services:
        service_name, description = MONDAY_TOGGLE_SERVICES.get(
            user_service.service, (user_service.service.title(), "")
        )
        icon, state = ("✅", "Enabled") if user_service.enabled else ("○", "Disabled")

        lines.append(
            f"{icon} <b>{service_name}</b> - {description}\n"
            f"   {state} · /{user_service.service} to toggle"
        )

        lines.append("")

    for command, (service_name, description) in MONDAY_LONG_RUNNING_SERVICES.items():
        lines.append(
            f"✅ <b>{service_name}</b> - {description}\n"
            f"   Always Available · /{command} to run"
        )
        lines.append("")

    return "\n".join(lines)


async def send_service_overview(update: Update) -> None:
    """Fetch the user's services and send their current enabled/disabled states."""

    # Some Telegram updates do not contain a normal message.
    if update.message is None:
        return

    user = update.effective_user
    if user is None:
        return

    user_services = get_user_services(user.id)

    if user_services is None:
        await update.message.reply_text(
            SERVICE_STATE_FAILED_TEXT,
            parse_mode="HTML",
        )
        return

    await update.message.reply_text(
        format_service_overview(user_services),
        parse_mode="HTML",
    )


async def handle_register(
    update: Update,
    _context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Create user account if user is not registered with Monday"""

    if update.message is None:
        return

    user = update.effective_user
    chat = update.effective_chat

    if user is None or chat is None:
        logger.error(
            f"/start triggered without effective user or chat. Effective user: {user}, Effective chat: {chat}"
        )
        return

    # Existing users do not need to be registered again.
    if get_user(user.id) is not None:
        logger.info(
            f"User {user.id} (@{user.username}) is already registered",
        )

        await update.message.reply_text(
            ALREADY_REGISTERED_TEXT,
            parse_mode="HTML",
        )

        await send_service_overview(update)
        return

    # user is not registered yet, begin onboarding
    logger.info(f"Onboarding new user {user.id} (@{user.username})...")

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

    # check if user is authenticated
    is_user_registered = True if get_user(update.effective_user.id) else False
    if not is_user_registered:
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

    if update.message is None or update.effective_user is None:
        return ConversationHandler.END

    user = update.effective_user

    service = (update.message.text or "").split()[0].lstrip("/").split("@")[0]

    is_user_registered = True if get_user(user.id) else False

    if not is_user_registered:
        await update.message.reply_text(
            NOT_REGISTERED_TEXT,
            parse_mode="HTML",
        )
        return ConversationHandler.END

    user_services = get_user_services(user.id)

    if user_services is None:
        await update.message.reply_text(
            SERVICE_STATE_FAILED_TEXT,
            parse_mode="HTML",
        )
        return ConversationHandler.END

    # we use current_state here to account for empty list handling
    current_state = next(
        (
            user_service.enabled
            for user_service in user_services
            if user_service.service == service
        ),
        None,
    )

    if current_state is None:
        logger.error(f"User {user.id} has no row for service {service}")
        await update.message.reply_text(
            SERVICE_STATE_FAILED_TEXT,
            parse_mode="HTML",
        )
        return ConversationHandler.END

    new_state = not current_state

    # Canvas services need the user's Canvas key before they can be enabled.
    if service in CANVAS_DEPENDENT_SERVICES and new_state:
        has_canvas_key = has_credential(user.id, "canvas")
        if has_canvas_key is None:
            logger.error(
                f"Error checking Canvas API key for {user.id}...",
            )
            await update.message.reply_text(
                SERVICE_STATE_FAILED_TEXT,
                parse_mode="HTML",
            )
            await send_service_overview(update)
            return ConversationHandler.END

        if not has_canvas_key:
            return await prompt_canvas_auth(update, context, service)

    if await set_service_and_reply(update, user.id, service, new_state):
        await send_service_overview(update)

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
    """Run the Canvas key check, then continue the service that asked for it."""

    result = await receive_canvas_api_key(update)
    if result is CanvasAuthResult.RETRY:
        return AWAITING_CANVAS_API_KEY

    service = pop_pending_service(context)

    # End flow without a saved key, still update user on current state of services
    if result is CanvasAuthResult.FAILED:
        await send_service_overview(update)
        return ConversationHandler.END

    # long running services aren't enabled; they carry on with their own next step.
    continue_service = ON_DEMAND_AFTER_CANVAS_AUTH.get(service or "")
    if continue_service is not None:
        await continue_service(update)
        return ConversationHandler.END

    # if it wasn't a long running service, but instead a toggle service like mcqueen or hermione, then we set_service_and_reply
    if update.effective_user is not None:
        if service is None:
            logger.error(
                f"Canvas connected for user {update.effective_user.id} (@{update.effective_user.username}) but no service was waiting on it"
            )
        else:
            await set_service_and_reply(update, update.effective_user.id, service, True)

    await send_service_overview(update)
    return ConversationHandler.END


async def handle_walle(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle /walle: show the user's Canvas courses, connecting Canvas first if needed."""

    if update.message is None or update.effective_user is None:
        return ConversationHandler.END

    user = update.effective_user

    if get_user(user.id) is None:
        await update.message.reply_text(
            NOT_REGISTERED_TEXT,
            parse_mode="HTML",
        )
        return ConversationHandler.END

    has_canvas_key = has_credential(user.id, "canvas")
    if has_canvas_key is None:
        logger.error(
            f"Not running Wall-E for user {user.id} (@{user.username}): could not check their Canvas key"
        )
        await update.message.reply_text(
            SERVICE_STATE_FAILED_TEXT,
            parse_mode="HTML",
        )
        return ConversationHandler.END

    if not has_canvas_key:
        return await prompt_canvas_auth(update, context, "walle")

    if await send_course_picker(update) is CoursePickerResult.KEY_REJECTED:
        return await prompt_canvas_auth(update, context, "walle")

    return ConversationHandler.END


def run_monday() -> None:
    """Starts polling the long-running Monday bot to listen to user commands"""

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
                    list(MONDAY_TOGGLE_SERVICES.keys()),
                    handle_service_toggle,
                ),
                CommandHandler(
                    "walle",
                    handle_walle,
                ),
            ],
            # If a function returns AWAITING_CANVAS_API_KEY,
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

    # Taps on Wall-E's course buttons.
    app.add_handler(
        CallbackQueryHandler(
            handle_course_selected,
            pattern=COURSE_CALLBACK_PATTERN,
        )
    )

    logger.info("MondayBot polling for updates")

    # run_polling manages its own event loop,
    # so don't call this from inside asyncio.run().
    app.run_polling()
