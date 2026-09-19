import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from config.settings import MCQUEEN_SERVICE, MONDAY_BOT_TOKEN
from db.service_credentials import (
    get_service_credentials,
    set_service_enabled,
)
from db.models import DbUserService
from db.users import get_user, try_create_user

logger = logging.getLogger(__name__)


SERVICE_COMMANDS: dict[str, str] = {
    "mcqueen": "mcqueen",
    "canvas": "canvas",
}


ALREADY_REGISTERED_TEXT = (
    "✅ <b>You're already set up!</b>\n\n"
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
    "👋 <b>Oops! You're not registered yet.</b>\n\n"
    "Run /start first to get set up."
)

SERVICE_STATE_FAILED_TEXT = (
    "⚠️ <b>Couldn't load your services</b>\n\n"
    "Please try again in a moment."
)

def format_service_overview(
    service_credentials: list[DbUserService],
) -> str:
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
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    del context

    # Edited messages and channel posts may arrive without .message.
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

    logger.info(
        "Registered user %s (@%s) with %s",
        user.id,
        user.username,
        MCQUEEN_SERVICE,
    )

    await update.message.reply_text(
        WELCOME_TEXT,
        parse_mode="HTML",
    )

    await send_service_overview(update)


async def handle_service_toggle(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    del context

    if update.message is None:
        return

    user = update.effective_user

    if user is None:
        return

    command = (
        (update.message.text or "")
        .split()[0]
        .lstrip("/")
        .split("@")[0]
    )

    service = SERVICE_COMMANDS.get(command)

    if service is None:
        return

    if get_user(user.id) is None:
        await update.message.reply_text(
            NOT_REGISTERED_TEXT,
            parse_mode="HTML",
        )
        return

    service_credentials = get_service_credentials(user.id)

    if service_credentials is None:
        await update.message.reply_text(
            SERVICE_STATE_FAILED_TEXT,
            parse_mode="HTML",
        )
        return

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
        return

    new_state = not current_state

    if not set_service_enabled(
        user.id,
        service,
        new_state,
    ):
        await update.message.reply_text(
            SERVICE_STATE_FAILED_TEXT,
            parse_mode="HTML",
        )
        return

    if new_state:
        await update.message.reply_text(
            f"✅ <b>{service.title()}</b> enabled.",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            f"○ <b>{service.title()}</b> disabled.",
            parse_mode="HTML",
        )

    await send_service_overview(update)


def run_monday() -> None:
    app = (
        Application.builder()
        .token(MONDAY_BOT_TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler(
            "start",
            handle_register,
        )
    )

    app.add_handler(
        CommandHandler(
            list(SERVICE_COMMANDS),
            handle_service_toggle,
        )
    )

    logger.info("MondayBot polling for updates")

    # run_polling manages its own event loop,
    # so don't call this from inside asyncio.run().
    app.run_polling()
