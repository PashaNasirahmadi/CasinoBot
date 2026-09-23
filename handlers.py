# -*- coding: utf-8 -*-
"""
handlers.py
تمام Command Handler ها و Callback Query Handler های ربات اینجا هستند.
"""

import asyncio
import time
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import config
import games
import utils
from database import db

logger = logging.getLogger(__name__)

# مجموعه‌ای برای جلوگیری از پردازش دوبار یک اکشن (Double Click) روی بازی‌های تک‌نفره.
# کلید: رشته یکتا برای هر اکشن (مثلاً f"dice:{message_id}")
_resolved_actions = set()


def _mark_resolved(action_key: str) -> bool:
    """اگر قبلاً پردازش شده True برنمی‌گرداند (یعنی نباید دوباره پردازش شود)."""
    if action_key in _resolved_actions:
        return False
    _resolved_actions.add(action_key)
    return True


async def ensure_user(update: Update):
    user = update.effective_user
    row, created = db.get_or_create_user(user.id, user.username or "", user.full_name or "")
    return row, created


async def error_handler(update, context: ContextTypes.DEFAULT_TYPE):
    """
    هندلر سراسری خطا. خطاهای شبکه‌ای (قطعی موقت اتصال به تلگرام، فیلترینگ و ...)
    را تمیز لاگ می‌کند تا ربات کرش نکند و فقط منتظر تلاش بعدی بماند.
    """
    from telegram.error import NetworkError, TimedOut

    error = context.error
    if isinstance(error, (NetworkError, TimedOut)):
        logger.warning("Network issue while talking to Telegram (will retry automatically): %s", error)
        return
    logger.error("Unhandled exception while processing an update: %s", error, exc_info=error)


def is_admin(user_id: int) -> bool:
    return config.ADMIN_ID != 0 and user_id == config.ADMIN_ID


# ==================================================
# /start
# ==================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row, created = await ensure_user(update)
    name = update.effective_user.first_name or "there"
    welcome = "🎉 Welcome" if created else "👋 Welcome back"
    text = (
        f"{welcome}, {name}!\n\n"
        f"This is a fun virtual economy & games bot — all tokens are just for fun, "
        f"with no real-world value.\n\n"
        f"💰 Silver: {utils.fmt_num(row['silver'])}\n"
        f"🥇 Gold: {utils.fmt_num(row['gold'])}\n"
        f"💎 Diamond: {utils.fmt_num(row['diamond'])}\n\n"
        f"Use the menu below to get started 👇"
    )
    await update.message.reply_text(text, reply_markup=utils.main_menu_keyboard())


# ==================================================
# Main menu callbacks
# ==================================================

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data.split(":", 1)[1]
    row, _ = await ensure_user(update)

    if action == "main":
        await query.edit_message_text(
            "🏠 Main Menu\n\nChoose an option below:", reply_markup=utils.main_menu_keyboard()
        )
    elif action == "games":
        await query.edit_message_text("🎮 Games Menu\n\nPick a game:", reply_markup=utils.games_menu_keyboard())
    elif action == "balance":
        await query.edit_message_text(utils.balance_text(row), reply_markup=utils.back_to_main_keyboard())
    elif action == "exchange":
        await show_exchange_menu(query)
    elif action == "leaderboard":
        await show_leaderboard_menu(query)
    elif action == "stats":
        await query.edit_message_text(utils.stats_text(row), reply_markup=utils.back_to_main_keyboard())
    elif action == "help":
        await query.edit_message_text(help_text(), reply_markup=utils.back_to_main_keyboard())
    elif action == "goldgames":
        await query.edit_message_text("🥇 Gold Games\n\nPick a game:", reply_markup=utils.gold_games_keyboard())
    elif action == "diamondgames":
        await query.edit_message_text(
            "💎 Diamond Games\n\nPick a game:", reply_markup=utils.diamond_games_keyboard()
        )


def help_text() -> str:
    return (
        "❓ HELP\n\n"
        "/start — open the main menu\n"
        "/gain — claim your free daily Silver (once every 24h)\n"
        "/bet <amount> — create a 1v1 Silver bet for others to join\n"
        "/dice <amount> — play Dice with Silver\n"
        "/numguess <amount> — play Number Guess with Silver\n"
        "/rps <amount> — challenge someone to Rock Paper Scissors (Gold, Best of 3)\n"
        "/survivor <amount> — start a Last Survivor game (Diamond)\n"
        "/survivorgold <amount> — start a mini Last Survivor game (Gold)\n"
        "/slots <amount> — play the Slot Machine with Silver\n"
        "/tictactoe (or /ttt) — start a 1v1 Tic-Tac-Toe game, just for fun\n\n"
        "All tokens (Silver, Gold, Diamond) are 100% virtual and only exist inside this bot "
        "for fun — no real money is involved."
    )


GAME_INFO_TEXTS = {
    "bet": lambda: (
        f"🎲 Bet\n\nUsage: /bet <amount>\n"
        f"Min: {config.BET_MIN_AMOUNT}, Max: {config.BET_MAX_AMOUNT}\n\n"
        f"Creates a 1v1 Silver bet — anyone else can tap Join to play against you."
    ),
    "dice": lambda: (
        f"🎲 Dice\n\nUsage: /dice <amount>\n"
        f"Min: {config.DICE_MIN_BET}, Max: {config.DICE_MAX_BET}\n\n"
        f"Guess Even/Odd (x{config.DICE_EVEN_ODD_MULTIPLIER}) or the exact roll (x{config.DICE_EXACT_MULTIPLIER})."
    ),
    "numguess": lambda: (
        f"🔢 Number Guess\n\nUsage: /numguess <amount>\n"
        f"Min: {config.NUMBER_GUESS_MIN_BET}, Max: {config.NUMBER_GUESS_MAX_BET}\n\n"
        f"Pick a range and guess the number — harder ranges pay more."
    ),
    "wordguess": lambda: None,  # مقدار جدا مدیریت می‌شود (نیازی به amount ندارد)
    "rps": lambda: (
        f"✊✋✌️ Rock Paper Scissors (Best of {2 * config.RPS_ROUNDS_TO_WIN - 1})\n\n"
        f"Usage: /rps <amount>\n"
        f"Min: {config.RPS_MIN_BET}, Max: {config.RPS_MAX_BET} Gold\n\n"
        f"First to {config.RPS_ROUNDS_TO_WIN} round wins takes the match."
    ),
    "survivordiamond": lambda: (
        f"💎 Last Survivor\n\nUsage: /survivor <amount>\n"
        f"Min: {config.SURVIVOR_DIAMOND_MIN_STAKE}, Max: {config.SURVIVOR_DIAMOND_MAX_STAKE} Diamond\n"
        f"Players: {config.SURVIVOR_DIAMOND_MIN_PLAYERS}-{config.SURVIVOR_DIAMOND_MAX_PLAYERS}"
    ),
    "survivorgold": lambda: (
        f"🥇 Gold Last Survivor\n\nUsage: /survivorgold <amount>\n"
        f"Min: {config.SURVIVOR_GOLD_MIN_STAKE}, Max: {config.SURVIVOR_GOLD_MAX_STAKE} Gold\n"
        f"Players: {config.SURVIVOR_GOLD_MIN_PLAYERS}-{config.SURVIVOR_GOLD_MAX_PLAYERS}"
    ),
    "slots": lambda: (
        f"🎰 Slot Machine\n\nUsage: /slots <amount>\n"
        f"Min: {config.SLOTS_MIN_BET}, Max: {config.SLOTS_MAX_BET} Silver\n\n"
        f"Match the middle row (payline) to win — 3 of a kind pays big, 2 of a kind pays small."
    ),
    "tictactoe": lambda: (
        "❌⭕ Tic-Tac-Toe\n\n"
        "Usage: /tictactoe (or /ttt)\n\n"
        "No stake required — just for fun, and it's tracked in your Statistics."
    ),
}


async def game_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر دکمه‌های داخل منوی Games — برای هر بازی یا راهنمای استفاده نشان می‌دهد یا مستقیم وارد بازی می‌شود."""
    query = update.callback_query
    parts = query.data.split(":")
    key = parts[1]

    if key == "wordguess":
        # Word Guess نیاز به amount ندارد، پس می‌تواند مستقیم از منو اجرا شود
        await wordguess_entry(update, context)
        return

    await query.answer()
    text_fn = GAME_INFO_TEXTS.get(key)
    text = text_fn() if text_fn else "Unknown game."
    await query.edit_message_text(text, reply_markup=utils.back_to_games_keyboard())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_user(update)
    await update.message.reply_text(help_text(), reply_markup=utils.back_to_main_keyboard())


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row, _ = await ensure_user(update)
    await update.message.reply_text(utils.balance_text(row), reply_markup=utils.back_to_main_keyboard())


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row, _ = await ensure_user(update)
    await update.message.reply_text(utils.stats_text(row), reply_markup=utils.back_to_main_keyboard())


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row, _ = await ensure_user(update)
    await update.message.reply_text(utils.profile_text(row), reply_markup=utils.back_to_main_keyboard())


# ==================================================
# /gain
# ==================================================

async def gain_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row, _ = await ensure_user(update)
    user_id = row["user_id"]
    now = time.time()
    last_gain = row["last_gain"]
    cooldown_seconds = config.GAIN_COOLDOWN_HOURS * 3600

    if last_gain is not None and (now - last_gain) < cooldown_seconds:
        remaining = cooldown_seconds - (now - last_gain)
        await update.message.reply_text(
            f"⏳ Daily Reward\n\nYou already claimed today's reward.\n"
            f"Next reward available in: {utils.fmt_seconds(remaining)}"
        )
        return

    import random

    amount = random.randint(config.GAIN_MIN_AMOUNT, config.GAIN_MAX_AMOUNT)

    with db.transaction() as conn:
        db.adjust_balance(conn, user_id, "silver", amount)
        db.set_last_gain(conn, user_id, now)

    await update.message.reply_text(
        f"🎁 Daily Reward\n\nYou received:\n💰 {amount} Silver\n\n"
        f"Next reward available in: {config.GAIN_COOLDOWN_HOURS}h 0m"
    )


# ==================================================
# Exchange
# ==================================================

async def show_exchange_menu(query):
    rate_gold = config.EXCHANGE_RATES["silver_to_gold"]
    rate_diamond = config.EXCHANGE_RATES["silver_to_diamond"]
    text = (
        "🏦 EXCHANGE\n\n"
        f"{rate_gold} Silver → 1 🥇 Gold\n"
        f"{rate_diamond} Silver → 1 💎 Diamond\n\n"
        "Use the commands below to exchange:\n"
        f"/exchange_gold <silver_amount>\n"
        f"/exchange_diamond <silver_amount>\n\n"
        f"Example: /exchange_gold {rate_gold * 3}  →  gives you 3 Gold"
    )
    await query.edit_message_text(text, reply_markup=utils.back_to_main_keyboard())


def exchange_command_factory(target_currency: str):
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        row, _ = await ensure_user(update)
        if not context.args:
            rate = config.EXCHANGE_RATES[f"silver_to_{target_currency}"]
            await update.message.reply_text(
                f"Usage: /exchange_{target_currency} <silver_amount>\n"
                f"Rate: {rate} Silver → 1 {target_currency.capitalize()}"
            )
            return
        try:
            amount = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number.")
            return
        if amount <= 0:
            await update.message.reply_text("❌ Amount must be positive.")
            return

        ok, msg, result = db.exchange_silver(row["user_id"], amount, target_currency)
        if not ok:
            await update.message.reply_text(msg)
            return

        emoji = "🥇" if target_currency == "gold" else "💎"
        await update.message.reply_text(
            f"✅ Exchange successful!\n\n💰 -{utils.fmt_num(amount)} Silver\n"
            f"{emoji} +{utils.fmt_num(result)} {target_currency.capitalize()}"
        )

    return handler


# ==================================================
# Leaderboard
# ==================================================

def leaderboard_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("💰 Richest Players", callback_data="lb:silver")],
        [InlineKeyboardButton("🏆 Most Wins", callback_data="lb:wins")],
        [InlineKeyboardButton("🎮 Most Games", callback_data="lb:games")],
        [InlineKeyboardButton("📈 Highest Win Rate", callback_data="lb:winrate")],
        [InlineKeyboardButton("💎 Most Diamonds", callback_data="lb:diamond")],
        [InlineKeyboardButton("🥇 Most Gold", callback_data="lb:gold")],
        [InlineKeyboardButton("⬅️ Main Menu", callback_data="menu:main")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def show_leaderboard_menu(query):
    await query.edit_message_text("🏆 Leaderboard\n\nChoose a category:", reply_markup=leaderboard_menu_keyboard())


LB_TITLES = {
    "silver": ("💰 Richest Players", "silver", "Silver"),
    "wins": ("🏆 Most Wins", "wins", "Wins"),
    "games": ("🎮 Most Games", "games_played", "Games"),
    "winrate": ("📈 Highest Win Rate", None, "Win Rate"),
    "diamond": ("💎 Most Diamonds", "diamond", "Diamond"),
    "gold": ("🥇 Most Gold", "gold", "Gold"),
}

MEDALS = ["👑", "🥈", "🥉"]


async def leaderboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data.split(":", 1)[1]
    title, field, label = LB_TITLES[category]
    rows = db.leaderboard(category, config.LEADERBOARD_TOP_N)

    lines = [f"{title}\n"]
    if not rows:
        lines.append("No data yet.")
    for i, r in enumerate(rows):
        medal = MEDALS[i] if i < 3 else f"{i + 1}."
        name = r["username"] or r["display_name"] or str(r["user_id"])
        if category == "winrate":
            games = r["games_played"]
            wins = r["wins"]
            value = f"{(wins / games * 100):.1f}% ({wins}/{games})"
        else:
            value = utils.fmt_num(r[field])
        lines.append(f"{medal} {name} — {value} {label if category != 'winrate' else ''}".rstrip())

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⬅️ Leaderboard", callback_data="menu:leaderboard")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="menu:main")],
        ]
    )
    await query.edit_message_text("\n".join(lines), reply_markup=keyboard)


# ==================================================
# BET (1v1 Silver bet)
# ==================================================

async def bet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row, _ = await ensure_user(update)
    if not db.is_game_enabled("bet"):
        await update.message.reply_text("🚫 Betting is currently disabled by the admin.")
        return

    if not context.args:
        await update.message.reply_text(f"Usage: /bet <amount>\nMin: {config.BET_MIN_AMOUNT}, Max: {config.BET_MAX_AMOUNT}")
        return
    try:
        stake = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number.")
        return

    if stake < config.BET_MIN_AMOUNT or stake > config.BET_MAX_AMOUNT:
        await update.message.reply_text(
            f"❌ Bet amount must be between {config.BET_MIN_AMOUNT} and {config.BET_MAX_AMOUNT}."
        )
        return

    if row["silver"] < stake:
        await update.message.reply_text("❌ You don't have enough Silver.")
        return

    try:
        bet_id = db.create_bet(row["user_id"], stake, update.effective_chat.id)
    except ValueError:
        await update.message.reply_text("❌ You don't have enough Silver.")
        return

    creator_name = utils.display_name_for(update.effective_user)
    text = (
        f"🎲 BET #{bet_id}\n\n"
        f"👤 Player: {creator_name}\n"
        f"💰 Stake: {utils.fmt_num(stake)} Silver\n\n"
        f"Waiting for opponent..."
    )
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🎮 Join Bet", callback_data=f"bet:join:{bet_id}")],
            [InlineKeyboardButton("❌ Cancel", callback_data=f"bet:cancel:{bet_id}")],
        ]
    )
    msg = await update.message.reply_text(text, reply_markup=keyboard)
    db.set_bet_message(bet_id, msg.message_id)


async def bet_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, action, bet_id_str = query.data.split(":")
    bet_id = int(bet_id_str)
    user = update.effective_user
    await ensure_user(update)

    if action == "join":
        action_key = f"bet_join:{bet_id}:{user.id}"
        if not _mark_resolved(action_key):
            await query.answer("Processing...", show_alert=False)
            return

        success, msg, bet = db.join_bet(bet_id, user.id)
        if not success:
            await query.answer(msg, show_alert=True)
            return

        await query.answer("✅ You joined the bet!")
        winner_name = "You" if bet["winner_id"] == user.id else None
        creator_row = db.get_user(bet["creator_id"])
        opponent_row = db.get_user(bet["opponent_id"])
        winner_row = creator_row if bet["winner_id"] == bet["creator_id"] else opponent_row
        loser_row = opponent_row if bet["winner_id"] == bet["creator_id"] else creator_row

        winner_name = winner_row["username"] or winner_row["display_name"]
        loser_name = loser_row["username"] or loser_row["display_name"]
        prize = bet["stake"] * 2

        text = (
            f"🎲 BET #{bet_id} — FINISHED\n\n"
            f"👤 Player 1: {creator_row['username'] or creator_row['display_name']}\n"
            f"👤 Player 2: {opponent_row['username'] or opponent_row['display_name']}\n"
            f"💰 Stake: {utils.fmt_num(bet['stake'])} Silver each\n\n"
            f"🏆 Winner: {winner_name} (+{utils.fmt_num(prize)} Silver)\n"
            f"💀 Loser: {loser_name} (-{utils.fmt_num(bet['stake'])} Silver)"
        )
        await query.edit_message_text(text)

    elif action == "cancel":
        if bet := db.get_bet(bet_id):
            pass
        success, msg = db.cancel_bet(bet_id, user.id)
        if not success:
            await query.answer(msg, show_alert=True)
            return
        await query.answer("Bet cancelled.")
        await query.edit_message_text(f"🎲 BET #{bet_id} — CANCELLED\n\nThe creator cancelled this bet.")


# ==================================================
# DICE
# ==================================================

async def dice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row, _ = await ensure_user(update)
    if not db.is_game_enabled("dice"):
        await update.message.reply_text("🚫 Dice is currently disabled by the admin.")
        return
    if not context.args:
        await update.message.reply_text(f"Usage: /dice <amount>\nMin: {config.DICE_MIN_BET}, Max: {config.DICE_MAX_BET}")
        return
    try:
        amount = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number.")
        return
    if amount < config.DICE_MIN_BET or amount > config.DICE_MAX_BET:
        await update.message.reply_text(
            f"❌ Amount must be between {config.DICE_MIN_BET} and {config.DICE_MAX_BET}."
        )
        return
    if row["silver"] < amount:
        await update.message.reply_text("❌ You don't have enough Silver.")
        return

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("⚫ Even", callback_data=f"dice:eo:even:{amount}"),
                InlineKeyboardButton("⚪ Odd", callback_data=f"dice:eo:odd:{amount}"),
            ],
            [InlineKeyboardButton("🎯 Guess Exact Number (x6)", callback_data=f"dice:exact:menu:{amount}")],
        ]
    )
    await update.message.reply_text(
        f"🎲 Dice — Stake: {utils.fmt_num(amount)} Silver\n\n"
        f"Guess Even/Odd (x{config.DICE_EVEN_ODD_MULTIPLIER} payout) "
        f"or the exact number 1-6 (x{config.DICE_EXACT_MULTIPLIER} payout):",
        reply_markup=keyboard,
    )


async def dice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split(":")
    row, _ = await ensure_user(update)
    user_id = row["user_id"]

    if parts[1] == "exact" and parts[2] == "menu":
        amount = int(parts[3])
        buttons = [
            InlineKeyboardButton(str(n), callback_data=f"dice:exact:{n}:{amount}") for n in range(1, 7)
        ]
        keyboard = InlineKeyboardMarkup([buttons[:3], buttons[3:]])
        await query.answer()
        await query.edit_message_text(
            f"🎯 Guess the exact number (1-6) — Stake: {utils.fmt_num(amount)} Silver",
            reply_markup=keyboard,
        )
        return

    action_key = f"dice:{query.message.message_id}"
    if not _mark_resolved(action_key):
        await query.answer("Already processed.", show_alert=False)
        return

    mode = parts[1]
    guess_raw = parts[2]
    amount = int(parts[3])

    current = db.get_user(user_id)
    if current["silver"] < amount:
        await query.answer("❌ You don't have enough Silver.", show_alert=True)
        return

    rolled = games.roll_dice()

    if mode == "eo":
        won = games.dice_even_odd_result(guess_raw, rolled)
        multiplier = config.DICE_EVEN_ODD_MULTIPLIER
        guess_display = guess_raw.capitalize()
    else:
        won = games.dice_exact_result(int(guess_raw), rolled)
        multiplier = config.DICE_EXACT_MULTIPLIER
        guess_display = f"Exact {guess_raw}"

    with db.transaction() as conn:
        if won:
            prize = amount * multiplier
            db.adjust_balance(conn, user_id, "silver", prize - amount)
            db.record_game_result(conn, user_id, True, "silver", prize - amount)
            result_line = f"🎉 You WIN! +{utils.fmt_num(prize - amount)} Silver"
        else:
            db.adjust_balance(conn, user_id, "silver", -amount)
            db.record_game_result(conn, user_id, False, "silver", amount)
            result_line = f"💀 You LOSE. -{utils.fmt_num(amount)} Silver"

    await query.answer()
    await query.edit_message_text(
        f"🎲 Dice Result\n\n"
        f"Your guess: {guess_display}\n"
        f"🎲 Rolled: {rolled}\n\n"
        f"{result_line}"
    )


# ==================================================
# NUMBER GUESS
# ==================================================

async def numguess_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row, _ = await ensure_user(update)
    if not db.is_game_enabled("number_guess"):
        await update.message.reply_text("🚫 Number Guess is currently disabled by the admin.")
        return
    if not context.args:
        await update.message.reply_text(
            f"Usage: /numguess <amount>\nMin: {config.NUMBER_GUESS_MIN_BET}, Max: {config.NUMBER_GUESS_MAX_BET}"
        )
        return
    try:
        amount = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number.")
        return
    if amount < config.NUMBER_GUESS_MIN_BET or amount > config.NUMBER_GUESS_MAX_BET:
        await update.message.reply_text(
            f"❌ Amount must be between {config.NUMBER_GUESS_MIN_BET} and {config.NUMBER_GUESS_MAX_BET}."
        )
        return
    if row["silver"] < amount:
        await update.message.reply_text("❌ You don't have enough Silver.")
        return

    keyboard_rows = []
    for key, info in config.NUMBER_GUESS_RANGES.items():
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    f"1-{info['max']} (x{info['multiplier']})",
                    callback_data=f"numguess:range:{key}:{amount}",
                )
            ]
        )
    await update.message.reply_text(
        f"🔢 Number Guess — Stake: {utils.fmt_num(amount)} Silver\n\nPick a difficulty:",
        reply_markup=InlineKeyboardMarkup(keyboard_rows),
    )


async def numguess_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split(":")
    row, _ = await ensure_user(update)
    user_id = row["user_id"]

    if parts[1] == "range":
        range_key = parts[2]
        amount = int(parts[3])
        info = config.NUMBER_GUESS_RANGES[range_key]
        max_val = info["max"]

        buttons = [
            InlineKeyboardButton(str(n), callback_data=f"numguess:pick:{range_key}:{n}:{amount}")
            for n in range(1, max_val + 1)
        ]
        rows = [buttons[i : i + 5] for i in range(0, len(buttons), 5)]
        await query.answer()
        await query.edit_message_text(
            f"🔢 Number Guess (1-{max_val}, x{info['multiplier']}) — Stake: {utils.fmt_num(amount)} Silver\n\n"
            f"Pick your number:",
            reply_markup=InlineKeyboardMarkup(rows),
        )
        return

    # parts[1] == "pick"
    action_key = f"numguess:{query.message.message_id}"
    if not _mark_resolved(action_key):
        await query.answer("Already processed.", show_alert=False)
        return

    range_key = parts[2]
    guess = int(parts[3])
    amount = int(parts[4])
    info = config.NUMBER_GUESS_RANGES[range_key]

    current = db.get_user(user_id)
    if current["silver"] < amount:
        await query.answer("❌ You don't have enough Silver.", show_alert=True)
        return

    picked = games.number_guess_pick(info["max"])
    won = picked == guess

    with db.transaction() as conn:
        if won:
            prize = amount * info["multiplier"]
            db.adjust_balance(conn, user_id, "silver", prize - amount)
            db.record_game_result(conn, user_id, True, "silver", prize - amount)
            result_line = f"🎉 You WIN! +{utils.fmt_num(prize - amount)} Silver"
        else:
            db.adjust_balance(conn, user_id, "silver", -amount)
            db.record_game_result(conn, user_id, False, "silver", amount)
            result_line = f"💀 You LOSE. -{utils.fmt_num(amount)} Silver"

    await query.answer()
    await query.edit_message_text(
        f"🔢 Number Guess Result (1-{info['max']})\n\n"
        f"Your guess: {guess}\n"
        f"🎯 The number was: {picked}\n\n"
        f"{result_line}"
    )


# ==================================================
# WORD GUESS
# ==================================================

def word_guess_difficulty_keyboard():
    keyboard = [
        [InlineKeyboardButton(f"🟢 Easy (+{config.WORD_GUESS_REWARDS['easy']})", callback_data="wordguess:diff:easy")],
        [InlineKeyboardButton(f"🟡 Medium (+{config.WORD_GUESS_REWARDS['medium']})", callback_data="wordguess:diff:medium")],
        [InlineKeyboardButton(f"🔴 Hard (+{config.WORD_GUESS_REWARDS['hard']})", callback_data="wordguess:diff:hard")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def wordguess_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هم از /wordguess و هم از دکمه منو صدا زده می‌شود."""
    if not db.is_game_enabled("word_guess"):
        text = "🚫 Word Guess is currently disabled by the admin."
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        return

    text = f"🔤 Word Guess — entry cost: {config.WORD_GUESS_BET} Silver\n\nChoose a difficulty:"
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=word_guess_difficulty_keyboard())
    else:
        await update.message.reply_text(text, reply_markup=word_guess_difficulty_keyboard())


async def wordguess_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split(":")
    row, _ = await ensure_user(update)
    user_id = row["user_id"]

    if parts[1] == "diff":
        difficulty = parts[2]
        cost = config.WORD_GUESS_BET
        current = db.get_user(user_id)
        if current["silver"] < cost:
            await query.answer("❌ You don't have enough Silver.", show_alert=True)
            return

        puzzle = games.pick_word(difficulty)
        # کلمه صحیح و مقدار شرط را در callback_data بازیکن بعدی رمزگذاری می‌کنیم
        buttons = [
            [InlineKeyboardButton(opt, callback_data=f"wordguess:pick:{difficulty}:{opt}:{puzzle['word']}")]
            for opt in puzzle["options"]
        ]
        await query.answer()
        await query.edit_message_text(
            f"🔤 Word Guess ({difficulty.capitalize()})\n\n"
            f"Entry cost: {cost} Silver (deducted now)\n"
            f"Guess the correct word from the options below:",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        # کسر هزینه ورود همین الان (چه ببرد چه ببازد این هزینه گرفته می‌شود)
        try:
            db.add_balance(user_id, "silver", -cost)
        except ValueError:
            pass
        return

    # parts[1] == "pick"
    action_key = f"wordguess:{query.message.message_id}"
    if not _mark_resolved(action_key):
        await query.answer("Already processed.", show_alert=False)
        return

    difficulty = parts[2]
    picked_option = parts[3]
    correct_word = parts[4]
    won = picked_option == correct_word

    with db.transaction() as conn:
        if won:
            reward = config.WORD_GUESS_REWARDS[difficulty]
            db.adjust_balance(conn, user_id, "silver", reward)
            db.record_game_result(conn, user_id, True, "silver", reward)
            result_line = f"🎉 Correct! +{utils.fmt_num(reward)} Silver"
        else:
            db.record_game_result(conn, user_id, False, "silver", config.WORD_GUESS_BET)
            result_line = f"💀 Wrong! The word was: {correct_word}"

    await query.answer()
    await query.edit_message_text(f"🔤 Word Guess Result ({difficulty.capitalize()})\n\n{result_line}")


# ==================================================
# ROCK PAPER SCISSORS (Gold, 2 players)
# ==================================================

RPS_EMOJI = {"rock": "✊", "paper": "✋", "scissors": "✌️"}


def rps_choice_keyboard(lobby_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✊ Rock", callback_data=f"rps:choose:{lobby_id}:rock"),
                InlineKeyboardButton("✋ Paper", callback_data=f"rps:choose:{lobby_id}:paper"),
                InlineKeyboardButton("✌️ Scissors", callback_data=f"rps:choose:{lobby_id}:scissors"),
            ]
        ]
    )


async def rps_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row, _ = await ensure_user(update)
    if not db.is_game_enabled("rps"):
        await update.message.reply_text("🚫 Rock Paper Scissors is currently disabled by the admin.")
        return
    if not context.args:
        await update.message.reply_text(f"Usage: /rps <amount>\nMin: {config.RPS_MIN_BET}, Max: {config.RPS_MAX_BET}")
        return
    try:
        stake = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number.")
        return
    if stake < config.RPS_MIN_BET or stake > config.RPS_MAX_BET:
        await update.message.reply_text(f"❌ Amount must be between {config.RPS_MIN_BET} and {config.RPS_MAX_BET}.")
        return
    if row["gold"] < stake:
        await update.message.reply_text("❌ You don't have enough Gold.")
        return

    try:
        lobby_id = db.create_lobby("rps", row["user_id"], stake, "gold", 2, update.effective_chat.id)
    except ValueError:
        await update.message.reply_text("❌ You don't have enough Gold.")
        return

    best_of = 2 * config.RPS_ROUNDS_TO_WIN - 1
    creator_name = utils.display_name_for(update.effective_user)
    text = (
        f"✊✋✌️ Rock Paper Scissors #{lobby_id} — Best of {best_of}\n\n"
        f"👤 Player: {creator_name}\n"
        f"🥇 Stake: {utils.fmt_num(stake)} Gold\n\n"
        f"Waiting for an opponent..."
    )
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🎮 Join", callback_data=f"rps:join:{lobby_id}")],
            [InlineKeyboardButton("❌ Cancel", callback_data=f"rps:cancel:{lobby_id}")],
        ]
    )
    msg = await update.message.reply_text(text, reply_markup=keyboard)
    db.set_lobby_message(lobby_id, msg.message_id)


async def rps_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split(":")
    action = parts[1]
    lobby_id = int(parts[2])
    user = update.effective_user
    await ensure_user(update)

    if action == "join":
        action_key = f"rps_join:{lobby_id}:{user.id}"
        if not _mark_resolved(action_key):
            await query.answer("Processing...", show_alert=False)
            return
        success, msg, lobby = db.join_lobby(lobby_id, user.id)
        if not success:
            await query.answer(msg, show_alert=True)
            return

        await query.answer("✅ Joined! Choose your move.")
        players = db.get_lobby_players(lobby_id)
        names = []
        for p in players:
            u = db.get_user(p["user_id"])
            names.append(u["username"] or u["display_name"])
        best_of = 2 * config.RPS_ROUNDS_TO_WIN - 1
        text = (
            f"✊✋✌️ Rock Paper Scissors #{lobby_id} — Best of {best_of}\n\n"
            f"👤 {names[0]}  vs  👤 {names[1]}\n"
            f"🥇 Stake: {utils.fmt_num(lobby['stake'])} Gold each\n\n"
            f"Round 1 — Score: {names[0]} 0 : 0 {names[1]}\n\n"
            f"Both players: tap your move below (kept secret until both choose)."
        )
        await query.edit_message_text(text, reply_markup=rps_choice_keyboard(lobby_id))

    elif action == "cancel":
        success, msg = db.cancel_lobby(lobby_id, user.id)
        if not success:
            await query.answer(msg, show_alert=True)
            return
        await query.answer("Cancelled.")
        await query.edit_message_text(f"✊✋✌️ Rock Paper Scissors #{lobby_id} — CANCELLED")

    elif action == "choose":
        choice = parts[3]
        players = db.get_lobby_players(lobby_id)
        player_ids = [p["user_id"] for p in players]
        if user.id not in player_ids:
            await query.answer("❌ You are not part of this game.", show_alert=True)
            return

        set_ok = db.try_set_choice(lobby_id, user.id, choice)
        if not set_ok:
            await query.answer("You already chose your move for this round.", show_alert=True)
            return

        await query.answer(f"You chose {RPS_EMOJI[choice]}. Waiting for opponent...")

        round_info = db.resolve_rps_round(lobby_id)
        if round_info is None:
            return  # هنوز حریف انتخاب نکرده

        lobby = db.get_lobby(lobby_id)
        p1_user = db.get_user(player_ids[0])
        p2_user = db.get_user(player_ids[1])
        p1_name = p1_user["username"] or p1_user["display_name"]
        p2_name = p2_user["username"] or p2_user["display_name"]
        p1_choice_emoji = RPS_EMOJI[round_info["p1_choice"]]
        p2_choice_emoji = RPS_EMOJI[round_info["p2_choice"]]

        if round_info["tie"]:
            text = (
                f"✊✋✌️ Rock Paper Scissors #{lobby_id} — Round {round_info['round']}\n\n"
                f"👤 {p1_name}: {p1_choice_emoji}\n"
                f"👤 {p2_name}: {p2_choice_emoji}\n\n"
                f"🤝 It's a tie! Replaying this round...\n\n"
                f"Score: {p1_name} {round_info['score_creator']} : {round_info['score_opponent']} {p2_name}"
            )
            await query.edit_message_text(text, reply_markup=rps_choice_keyboard(lobby_id))

        elif round_info["game_finished"]:
            match_winner_id = round_info["match_winner_id"]
            winner_user = p1_user if match_winner_id == player_ids[0] else p2_user
            loser_user = p2_user if match_winner_id == player_ids[0] else p1_user
            prize = lobby["stake"] * 2
            text = (
                f"✊✋✌️ Rock Paper Scissors #{lobby_id} — FINAL RESULT\n\n"
                f"Round {round_info['round']}: {p1_name} {p1_choice_emoji}  vs  {p2_name} {p2_choice_emoji}\n\n"
                f"📊 Final Score — {p1_name} {round_info['score_creator']} : "
                f"{round_info['score_opponent']} {p2_name}\n\n"
                f"🏆 Winner: {winner_user['username'] or winner_user['display_name']} "
                f"(+{utils.fmt_num(prize)} Gold)\n"
                f"💀 Loser: {loser_user['username'] or loser_user['display_name']} "
                f"(-{utils.fmt_num(lobby['stake'])} Gold)"
            )
            await query.edit_message_text(text)

        else:
            text = (
                f"✊✋✌️ Rock Paper Scissors #{lobby_id} — Round {round_info['round']} Result\n\n"
                f"👤 {p1_name}: {p1_choice_emoji}\n"
                f"👤 {p2_name}: {p2_choice_emoji}\n\n"
                f"📊 Score — {p1_name} {round_info['score_creator']} : {round_info['score_opponent']} {p2_name}\n\n"
                f"➡️ Round {round_info['round'] + 1}: choose your move!"
            )
            await query.edit_message_text(text, reply_markup=rps_choice_keyboard(lobby_id))


# ==================================================
# LAST SURVIVOR (Diamond, up to 6) & Gold Last Survivor (up to 3)
# ==================================================

SURVIVOR_CONFIGS = {
    "survivordiamond": {
        "game_type": "survivor_diamond",
        "currency": "diamond",
        "emoji": "💎",
        "min_players": config.SURVIVOR_DIAMOND_MIN_PLAYERS,
        "max_players": config.SURVIVOR_DIAMOND_MAX_PLAYERS,
        "min_stake": config.SURVIVOR_DIAMOND_MIN_STAKE,
        "max_stake": config.SURVIVOR_DIAMOND_MAX_STAKE,
        "round_delay": config.SURVIVOR_DIAMOND_ROUND_DELAY_SECONDS,
        "game_key": "survivor_diamond",
        "title": "💎 Last Survivor",
    },
    "survivorgold": {
        "game_type": "survivor_gold",
        "currency": "gold",
        "emoji": "🥇",
        "min_players": config.SURVIVOR_GOLD_MIN_PLAYERS,
        "max_players": config.SURVIVOR_GOLD_MAX_PLAYERS,
        "min_stake": config.SURVIVOR_GOLD_MIN_STAKE,
        "max_stake": config.SURVIVOR_GOLD_MAX_STAKE,
        "round_delay": config.SURVIVOR_GOLD_ROUND_DELAY_SECONDS,
        "game_key": "survivor_gold",
        "title": "🥇 Gold Last Survivor",
    },
}


def survivor_command_factory(kind: str):
    cfg = SURVIVOR_CONFIGS[kind]

    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        row, _ = await ensure_user(update)
        if not db.is_game_enabled(cfg["game_key"]):
            await update.message.reply_text(f"🚫 {cfg['title']} is currently disabled by the admin.")
            return
        if not context.args:
            await update.message.reply_text(
                f"Usage: /{kind} <amount>\nMin: {cfg['min_stake']}, Max: {cfg['max_stake']}\n"
                f"Players: {cfg['min_players']}-{cfg['max_players']}"
            )
            return
        try:
            stake = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number.")
            return
        if stake < cfg["min_stake"] or stake > cfg["max_stake"]:
            await update.message.reply_text(
                f"❌ Amount must be between {cfg['min_stake']} and {cfg['max_stake']}."
            )
            return
        if row[cfg["currency"]] < stake:
            await update.message.reply_text(f"❌ You don't have enough {cfg['currency'].capitalize()}.")
            return

        try:
            lobby_id = db.create_lobby(
                cfg["game_type"], row["user_id"], stake, cfg["currency"], cfg["max_players"], update.effective_chat.id
            )
        except ValueError:
            await update.message.reply_text(f"❌ You don't have enough {cfg['currency'].capitalize()}.")
            return

        text = survivor_lobby_text(cfg, lobby_id)
        keyboard = survivor_lobby_keyboard(kind, lobby_id)
        msg = await update.message.reply_text(text, reply_markup=keyboard)
        db.set_lobby_message(lobby_id, msg.message_id)

    return handler


def survivor_lobby_text(cfg, lobby_id):
    lobby = db.get_lobby(lobby_id)
    players = db.get_lobby_players(lobby_id)
    prize_pool = lobby["stake"] * len(players)
    lines = [f"{cfg['title']} #{lobby_id}\n"]
    for p in players:
        u = db.get_user(p["user_id"])
        name = u["username"] or u["display_name"]
        lines.append(f"👤 {name} → {utils.fmt_num(lobby['stake'])} {cfg['emoji']}")
    lines.append("")
    lines.append(f"Players: {len(players)}/{cfg['max_players']} (min {cfg['min_players']} to start)")
    lines.append(f"{cfg['emoji']} Prize Pool: {utils.fmt_num(prize_pool)} {cfg['currency'].capitalize()}")
    return "\n".join(lines)


def survivor_lobby_keyboard(kind, lobby_id):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🎮 Join", callback_data=f"{kind}:join:{lobby_id}")],
            [InlineKeyboardButton("▶️ Start Game", callback_data=f"{kind}:start:{lobby_id}")],
            [InlineKeyboardButton("❌ Cancel", callback_data=f"{kind}:cancel:{lobby_id}")],
        ]
    )


def survivor_callback_factory(kind: str):
    cfg = SURVIVOR_CONFIGS[kind]

    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        parts = query.data.split(":")
        action = parts[1]
        lobby_id = int(parts[2])
        user = update.effective_user
        await ensure_user(update)

        if action == "join":
            action_key = f"{kind}_join:{lobby_id}:{user.id}"
            if not _mark_resolved(action_key):
                await query.answer("Processing...", show_alert=False)
                return
            success, msg, lobby = db.join_lobby(lobby_id, user.id)
            if not success:
                await query.answer(msg, show_alert=True)
                return
            await query.answer("✅ Joined!")
            text = survivor_lobby_text(cfg, lobby_id)
            await query.edit_message_text(text, reply_markup=survivor_lobby_keyboard(kind, lobby_id))

        elif action == "cancel":
            success, msg = db.cancel_lobby(lobby_id, user.id)
            if not success:
                await query.answer(msg, show_alert=True)
                return
            await query.answer("Cancelled.")
            await query.edit_message_text(f"{cfg['title']} #{lobby_id} — CANCELLED, stakes refunded.")

        elif action == "start":
            success, msg = db.try_start_lobby(lobby_id, user.id)
            if not success:
                await query.answer(msg, show_alert=True)
                return
            await query.answer("🎮 Game starting!")
            await run_survivor_game(context, cfg, kind, lobby_id, query.message.chat_id, query.message.message_id)

    return handler


async def run_survivor_game(context, cfg, kind, lobby_id, chat_id, message_id):
    lobby = db.get_lobby(lobby_id)
    players = db.get_lobby_players(lobby_id)
    player_ids = [p["user_id"] for p in players]
    prize_pool = lobby["stake"] * len(player_ids)

    elimination_order = games.eliminate_order(player_ids)  # [0]=first eliminated ... [-1]=winner
    remaining = player_ids[:]
    round_num = 1

    async def edit(text):
        try:
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text)
        except Exception:
            logger.exception("Failed to edit survivor message")

    def name_of(uid):
        u = db.get_user(uid)
        return u["username"] or u["display_name"]

    await edit(
        f"{cfg['title']} #{lobby_id}\n\n"
        f"🎮 Game started with {len(remaining)} players!\n"
        f"{cfg['emoji']} Prize Pool: {utils.fmt_num(prize_pool)} {lobby['currency'].capitalize()}\n\n"
        f"Get ready..."
    )
    await asyncio.sleep(cfg["round_delay"])

    for eliminated_id in elimination_order[:-1]:
        remaining.remove(eliminated_id)
        text = (
            f"{cfg['title']} #{lobby_id}\n\n"
            f"🎯 Round {round_num}\n\n"
            f"Players remaining: {len(remaining)}\n\n"
            f"🎲 Random selection...\n\n"
            f"❌ Player {name_of(eliminated_id)} eliminated.\n\n"
            f"{cfg['emoji']} Prize Pool: {utils.fmt_num(prize_pool)} {lobby['currency'].capitalize()}"
        )
        await edit(text)
        round_num += 1
        await asyncio.sleep(cfg["round_delay"])

    winner_id = elimination_order[-1]
    db.finish_lobby_survivor(lobby_id, winner_id, prize_pool, lobby["currency"])

    final_text = (
        f"{cfg['title']} #{lobby_id} — FINISHED 🎉\n\n"
        f"🏆 Winner: {name_of(winner_id)}\n"
        f"{cfg['emoji']} Prize: {utils.fmt_num(prize_pool)} {lobby['currency'].capitalize()}"
    )
    await edit(final_text)


# ==================================================
# SLOT MACHINE
# ==================================================

async def slots_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row, _ = await ensure_user(update)
    if not db.is_game_enabled("slots"):
        await update.message.reply_text("🚫 Slot Machine is currently disabled by the admin.")
        return
    if not context.args:
        await update.message.reply_text(
            f"Usage: /slots <amount>\nMin: {config.SLOTS_MIN_BET}, Max: {config.SLOTS_MAX_BET}"
        )
        return
    try:
        amount = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number.")
        return
    if amount < config.SLOTS_MIN_BET or amount > config.SLOTS_MAX_BET:
        await update.message.reply_text(
            f"❌ Amount must be between {config.SLOTS_MIN_BET} and {config.SLOTS_MAX_BET}."
        )
        return
    if row["silver"] < amount:
        await update.message.reply_text("❌ You don't have enough Silver.")
        return

    user_id = row["user_id"]
    grid = games.spin_slots(config.SLOTS_ROWS, config.SLOTS_COLS)
    payline_index = config.SLOTS_ROWS // 2
    payline = grid[payline_index]
    multiplier, kind = games.evaluate_slots_payline(payline)

    # همه چیز داخل یک تراکنش اتمیک: اگر موجودی در همین لحظه کافی نباشد Exception
    # می‌گیرد و هیچ تغییری (نه کسر و نه واریز) اعمال نمی‌شود.
    try:
        with db.transaction() as conn:
            current = conn.execute("SELECT silver FROM users WHERE user_id = ?", (user_id,)).fetchone()
            if current is None or current["silver"] < amount:
                raise ValueError("Insufficient balance")

            if multiplier > 0:
                prize = round(amount * multiplier)
                net = prize - amount
                db.adjust_balance(conn, user_id, "silver", net)
                if net > 0:
                    db.record_game_result(conn, user_id, True, "silver", net)
                    kind_label = "Three of a Kind! 🎉" if kind == "three_of_a_kind" else "Two of a Kind!"
                    result_line = f"{kind_label} +{utils.fmt_num(net)} Silver"
                else:
                    # push (سود صفر): نه برد نه باخت، فقط شرط برگشت داده می‌شود
                    result_line = f"🤝 Push — your {utils.fmt_num(amount)} Silver was returned."
            else:
                db.adjust_balance(conn, user_id, "silver", -amount)
                db.record_game_result(conn, user_id, False, "silver", amount)
                result_line = f"💀 No match. -{utils.fmt_num(amount)} Silver"
    except ValueError:
        await update.message.reply_text("❌ You don't have enough Silver.")
        return

    grid_text = utils.format_slots_grid(grid, payline_index)
    text = (
        "🎰 SLOT MACHINE\n\n"
        f"{grid_text}\n\n"
        f"💰 Bet: {utils.fmt_num(amount)} Silver\n"
        f"🎯 Result: {result_line}"
    )
    await update.message.reply_text(text)


# ==================================================
# TIC-TAC-TOE (دوز، دو نفره، بدون شرط)
# ==================================================

TTT_NUMBERS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]


def ttt_lobby_keyboard(game_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🎮 Join Game", callback_data=f"ttt:join:{game_id}")],
            [InlineKeyboardButton("❌ Cancel", callback_data=f"ttt:cancel:{game_id}")],
        ]
    )


def ttt_board_keyboard(game_id: int, board: str) -> InlineKeyboardMarkup:
    rows = []
    for r in range(3):
        row_buttons = []
        for c in range(3):
            idx = r * 3 + c
            cell = board[idx]
            if cell == ".":
                row_buttons.append(
                    InlineKeyboardButton(TTT_NUMBERS[idx], callback_data=f"ttt:move:{game_id}:{idx}")
                )
            else:
                label = "❌" if cell == "X" else "⭕"
                row_buttons.append(InlineKeyboardButton(label, callback_data="ttt:taken"))
        rows.append(row_buttons)
    return InlineKeyboardMarkup(rows)


def ttt_active_text(game, x_name: str, o_name: str) -> str:
    turn_name = x_name if game["turn"] == "X" else o_name
    turn_symbol = "❌" if game["turn"] == "X" else "⭕"
    return (
        f"❌⭕ Tic-Tac-Toe #{game['game_id']}\n\n"
        f"❌ Player 1: {x_name}\n"
        f"⭕ Player 2: {o_name}\n\n"
        f"👉 Turn: {turn_symbol} {turn_name}"
    )


async def tictactoe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row, _ = await ensure_user(update)
    if not db.is_game_enabled("tictactoe"):
        await update.message.reply_text("🚫 Tic-Tac-Toe is currently disabled by the admin.")
        return

    existing = db.get_active_ttt_for_user(row["user_id"])
    if existing:
        await update.message.reply_text(
            f"❌ You already have an active Tic-Tac-Toe game (#{existing['game_id']}). "
            f"Finish it or cancel it before starting a new one."
        )
        return

    game_id = db.create_ttt_game(row["user_id"], update.effective_chat.id)
    creator_name = utils.display_name_for(update.effective_user)
    text = (
        f"🎮 Tic-Tac-Toe #{game_id}\n\n"
        f"❌ {creator_name} is waiting for a second player...\n\n"
        f"Tap below to join as ⭕"
    )
    msg = await update.message.reply_text(text, reply_markup=ttt_lobby_keyboard(game_id))
    db.set_ttt_message(game_id, msg.message_id)


async def ttt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user = update.effective_user
    await ensure_user(update)

    if data == "ttt:taken":
        await query.answer("That cell is already taken.", show_alert=False)
        return

    parts = data.split(":")
    action = parts[1]
    game_id = int(parts[2])

    if action == "join":
        action_key = f"ttt_join:{game_id}:{user.id}"
        if not _mark_resolved(action_key):
            await query.answer("Processing...", show_alert=False)
            return

        existing = db.get_active_ttt_for_user(user.id)
        if existing and existing["game_id"] != game_id:
            await query.answer(
                f"❌ You already have another active Tic-Tac-Toe game (#{existing['game_id']}).",
                show_alert=True,
            )
            return

        success, msg, game = db.join_ttt_game(game_id, user.id)
        if not success:
            await query.answer(msg, show_alert=True)
            return

        await query.answer("✅ You joined! You are ⭕")
        x_user = db.get_user(game["player_x"])
        o_user = db.get_user(game["player_o"])
        x_name = x_user["username"] or x_user["display_name"]
        o_name = o_user["username"] or o_user["display_name"]
        text = ttt_active_text(game, x_name, o_name)
        await query.edit_message_text(text, reply_markup=ttt_board_keyboard(game_id, game["board"]))

    elif action == "cancel":
        success, msg = db.cancel_ttt_game(game_id, user.id)
        if not success:
            await query.answer(msg, show_alert=True)
            return
        await query.answer("Cancelled.")
        await query.edit_message_text(f"❌⭕ Tic-Tac-Toe #{game_id} — CANCELLED")

    elif action == "move":
        cell_index = int(parts[3])
        success, msg, game, finished, winner_id, is_draw = db.make_ttt_move(game_id, user.id, cell_index)
        if not success:
            await query.answer(msg, show_alert=True)
            return
        await query.answer()

        x_user = db.get_user(game["player_x"])
        o_user = db.get_user(game["player_o"])
        x_name = x_user["username"] or x_user["display_name"]
        o_name = o_user["username"] or o_user["display_name"]

        if finished:
            board_display = utils.format_ttt_board(game["board"])
            if is_draw:
                text = f"❌⭕ Tic-Tac-Toe #{game_id}\n\n{board_display}\n\n🤝 Draw!"
            else:
                winner_name = x_name if winner_id == game["player_x"] else o_name
                loser_name = o_name if winner_id == game["player_x"] else x_name
                winner_symbol = "❌" if winner_id == game["player_x"] else "⭕"
                loser_symbol = "⭕" if winner_id == game["player_x"] else "❌"
                text = (
                    f"❌⭕ Tic-Tac-Toe #{game_id}\n\n{board_display}\n\n"
                    f"🏆 Game Over!\n\n"
                    f"{winner_symbol} {winner_name} — Winner\n"
                    f"{loser_symbol} {loser_name} — Loser"
                )
            await query.edit_message_text(text)
        else:
            text = ttt_active_text(game, x_name, o_name)
            await query.edit_message_text(text, reply_markup=ttt_board_keyboard(game_id, game["board"]))


# ==================================================
# Background job: expire old bets / lobbies
# ==================================================

async def cleanup_job(context: ContextTypes.DEFAULT_TYPE):
    expired_bets = db.expire_old_bets(config.BET_EXPIRE_MINUTES)
    for bet in expired_bets:
        try:
            await context.bot.edit_message_text(
                chat_id=bet["chat_id"],
                message_id=bet["message_id"],
                text=f"🎲 BET #{bet['bet_id']} — EXPIRED\n\nNo opponent joined in time. Silver refunded.",
            )
        except Exception:
            pass

    expired_lobbies = db.expire_old_lobbies(config.SURVIVOR_LOBBY_TIMEOUT_MINUTES)
    for lobby in expired_lobbies:
        try:
            await context.bot.edit_message_text(
                chat_id=lobby["chat_id"],
                message_id=lobby["message_id"],
                text=f"Lobby #{lobby['lobby_id']} — EXPIRED\n\nNot enough players joined in time. Stakes refunded.",
            )
        except Exception:
            pass


# ==================================================
# ADMIN PANEL
# ==================================================

def admin_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("📊 Stats", callback_data="admin:stats")],
        [InlineKeyboardButton("🎮 Toggle Games", callback_data="admin:games")],
        [InlineKeyboardButton("⬅️ Close", callback_data="admin:close")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    text = (
        "🛠 ADMIN PANEL\n\n"
        "Commands:\n"
        "/admin_add <user_id> <silver|gold|diamond> <amount>\n"
        "/admin_remove <user_id> <silver|gold|diamond> <amount>\n"
        "/admin_reset <user_id>\n\n"
        "Or use the buttons below:"
    )
    await update.message.reply_text(text, reply_markup=admin_menu_keyboard())


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(update.effective_user.id):
        await query.answer("❌ Not authorized.", show_alert=True)
        return
    await query.answer()
    action = query.data.split(":", 1)[1]

    if action == "stats":
        stats = db.admin_stats()
        text = (
            "📊 ADMIN STATS\n\n"
            f"👥 Users: {utils.fmt_num(stats['users'])}\n"
            f"🎮 Total games played: {utils.fmt_num(stats['games'])}\n\n"
            f"💰 Total Silver: {utils.fmt_num(stats['total_silver'])}\n"
            f"🥇 Total Gold: {utils.fmt_num(stats['total_gold'])}\n"
            f"💎 Total Diamond: {utils.fmt_num(stats['total_diamond'])}"
        )
        await query.edit_message_text(text, reply_markup=admin_menu_keyboard())

    elif action == "games":
        statuses = db.all_game_statuses()
        keyboard = []
        for key, enabled in statuses.items():
            label = f"{'✅' if enabled else '⛔️'} {key}"
            keyboard.append([InlineKeyboardButton(label, callback_data=f"admin:toggle:{key}")])
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="admin:back")])
        await query.edit_message_text("🎮 Toggle Games (tap to flip on/off):", reply_markup=InlineKeyboardMarkup(keyboard))

    elif action.startswith("toggle:"):
        game_key = action.split(":", 1)[1]
        current = db.is_game_enabled(game_key)
        db.set_game_status(update.effective_user.id, game_key, not current)
        statuses = db.all_game_statuses()
        keyboard = []
        for key, enabled in statuses.items():
            label = f"{'✅' if enabled else '⛔️'} {key}"
            keyboard.append([InlineKeyboardButton(label, callback_data=f"admin:toggle:{key}")])
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="admin:back")])
        await query.edit_message_text("🎮 Toggle Games (tap to flip on/off):", reply_markup=InlineKeyboardMarkup(keyboard))

    elif action == "back":
        await query.edit_message_text("🛠 ADMIN PANEL", reply_markup=admin_menu_keyboard())

    elif action == "close":
        await query.edit_message_text("🛠 Admin panel closed.")


async def admin_add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _admin_adjust(update, context, sign=1)


async def admin_remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _admin_adjust(update, context, sign=-1)


async def _admin_adjust(update: Update, context: ContextTypes.DEFAULT_TYPE, sign: int):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    if len(context.args) != 3:
        cmd = "admin_add" if sign == 1 else "admin_remove"
        await update.message.reply_text(f"Usage: /{cmd} <user_id> <silver|gold|diamond> <amount>")
        return
    try:
        target_id = int(context.args[0])
        currency = context.args[1].lower()
        amount = int(context.args[2])
    except ValueError:
        await update.message.reply_text("❌ Invalid arguments.")
        return
    if currency not in ("silver", "gold", "diamond"):
        await update.message.reply_text("❌ Currency must be silver, gold or diamond.")
        return
    if amount <= 0:
        await update.message.reply_text("❌ Amount must be positive.")
        return

    ok, result = db.admin_adjust_balance(update.effective_user.id, target_id, currency, sign * amount)
    if not ok:
        await update.message.reply_text(result)
        return
    verb = "added to" if sign == 1 else "removed from"
    await update.message.reply_text(
        f"✅ {utils.fmt_num(amount)} {currency.capitalize()} {verb} user {target_id}.\n"
        f"New balance: {utils.fmt_num(result)} {currency.capitalize()}"
    )


async def admin_reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /admin_reset <user_id>")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user id.")
        return
    ok, msg = db.admin_reset_user(update.effective_user.id, target_id)
    await update.message.reply_text(msg)


# ==================================================
# Fallback for unknown callback data (safety net)
# ==================================================

async def unknown_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("This button is not available anymore.", show_alert=False)
