# -*- coding: utf-8 -*-
"""
bot.py
نقطه ورود اصلی. اجرای این فایل ربات را بالا می‌آورد:

    python bot.py
"""

import logging

from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
)

import config
import handlers
import city

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def build_application() -> Application:
    if not config.BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is not set. Copy .env.example to .env and set your bot token."
        )

    builder = ApplicationBuilder().token(config.BOT_TOKEN)

    if config.PROXY_URL:
        # هم برای درخواست‌های عادی (sendMessage و ...) و هم برای long-polling (getUpdates)
        # از پراکسی استفاده می‌شود. برای socks5 باید httpx[socks] نصب باشد:
        #   pip install "httpx[socks]"
        builder = builder.proxy(config.PROXY_URL).get_updates_proxy(config.PROXY_URL)
        logger.info("Using proxy: %s", config.PROXY_URL)

    app = builder.build()

    # -------------------- Commands --------------------
    app.add_handler(CommandHandler("start", handlers.start_command))
    app.add_handler(CommandHandler("help", handlers.help_command))
    app.add_handler(CommandHandler("balance", handlers.balance_command))
    app.add_handler(CommandHandler("stats", handlers.stats_command))
    app.add_handler(CommandHandler("profile", handlers.profile_command))
    app.add_handler(CommandHandler("gain", handlers.gain_command))

    app.add_handler(CommandHandler("bet", handlers.bet_command))
    app.add_handler(CommandHandler("dice", handlers.dice_command))
    app.add_handler(CommandHandler("numguess", handlers.numguess_command))
    app.add_handler(CommandHandler("wordguess", handlers.wordguess_entry))
    app.add_handler(CommandHandler("rps", handlers.rps_command))
    app.add_handler(CommandHandler("survivor", handlers.survivor_command_factory("survivordiamond")))
    app.add_handler(CommandHandler("survivorgold", handlers.survivor_command_factory("survivorgold")))
    app.add_handler(CommandHandler("slots", handlers.slots_command))
    app.add_handler(CommandHandler("tictactoe", handlers.tictactoe_command))
    app.add_handler(CommandHandler("ttt", handlers.tictactoe_command))
    app.add_handler(CommandHandler("city", city.city_command))

    # Exchange commands (built dynamically via a small factory function)
    app.add_handler(CommandHandler("exchange_gold", handlers.exchange_command_factory("gold")))
    app.add_handler(CommandHandler("exchange_diamond", handlers.exchange_command_factory("diamond")))

    # Admin commands
    app.add_handler(CommandHandler("admin", handlers.admin_command))
    app.add_handler(CommandHandler("admin_add", handlers.admin_add_command))
    app.add_handler(CommandHandler("admin_remove", handlers.admin_remove_command))
    app.add_handler(CommandHandler("admin_reset", handlers.admin_reset_command))

    # -------------------- Callback queries --------------------
    app.add_handler(CallbackQueryHandler(handlers.menu_callback, pattern=r"^menu:"))
    app.add_handler(CallbackQueryHandler(handlers.game_menu_callback, pattern=r"^game:"))
    app.add_handler(CallbackQueryHandler(handlers.leaderboard_callback, pattern=r"^lb:"))
    app.add_handler(CallbackQueryHandler(handlers.bet_callback, pattern=r"^bet:"))
    app.add_handler(CallbackQueryHandler(handlers.dice_callback, pattern=r"^dice:"))
    app.add_handler(CallbackQueryHandler(handlers.numguess_callback, pattern=r"^numguess:"))
    app.add_handler(CallbackQueryHandler(handlers.wordguess_callback, pattern=r"^wordguess:"))
    app.add_handler(CallbackQueryHandler(handlers.rps_callback, pattern=r"^rps:"))
    app.add_handler(CallbackQueryHandler(handlers.ttt_callback, pattern=r"^ttt:"))
    app.add_handler(CallbackQueryHandler(city.city_callback, pattern=r"^city:"))
    app.add_handler(
        CallbackQueryHandler(handlers.survivor_callback_factory("survivordiamond"), pattern=r"^survivordiamond:")
    )
    app.add_handler(
        CallbackQueryHandler(handlers.survivor_callback_factory("survivorgold"), pattern=r"^survivorgold:")
    )
    app.add_handler(CallbackQueryHandler(handlers.admin_callback, pattern=r"^admin:"))
    # Fallback: any other callback data that didn't match above
    app.add_handler(CallbackQueryHandler(handlers.unknown_callback))

    # -------------------- Global error handler --------------------
    app.add_error_handler(handlers.error_handler)

    # -------------------- Background jobs --------------------
    if app.job_queue is not None:
        app.job_queue.run_repeating(handlers.cleanup_job, interval=300, first=60)
        app.job_queue.run_repeating(
            city.city_settlement_job, interval=config.CITY_SETTLEMENT_JOB_INTERVAL_SECONDS, first=90
        )
    else:
        logger.warning(
            "JobQueue is not available (install 'python-telegram-bot[job-queue]') — "
            "expired bets/lobbies won't be auto-refunded in the background."
        )

    return app


def main():
    # Python 3.14 removed the old behavior where asyncio.get_event_loop() would
    # silently create a new loop if none existed. python-telegram-bot's run_polling()
    # still relies on that old behavior internally, so on 3.14+ we create the loop
    # ourselves beforehand. This is a no-op / harmless on Python <= 3.13.
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    app = build_application()
    logger.info("Bot is starting...")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
