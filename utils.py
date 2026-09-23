# -*- coding: utf-8 -*-
"""
utils.py
توابع کمکی مشترک: ساخت کیبوردها، فرمت پیام‌ها، فرمت زمان و اعداد.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def fmt_num(n) -> str:
    try:
        return f"{int(n):,}"
    except (ValueError, TypeError):
        return str(n)


def fmt_seconds(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    mins = seconds // 60
    secs = seconds % 60
    if mins > 0:
        return f"{mins}m {secs}s"
    return f"{secs}s"


def display_name_for(user) -> str:
    """user یک telegram.User است."""
    if user.username:
        return f"@{user.username}"
    return user.full_name


def back_to_games_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⬅️ Games", callback_data="menu:games")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="menu:main")],
        ]
    )


def format_slots_grid(grid, payline_index=None) -> str:
    """گرید اسلات را به شکل جعبه‌ای شبیه نمونه طراحی‌شده رندر می‌کند."""
    cols = len(grid[0])
    top = "┌" + "──────┬" * (cols - 1) + "──────┐"
    sep = "├" + "──────┼" * (cols - 1) + "──────┤"
    bottom = "└" + "──────┴" * (cols - 1) + "──────┘"

    lines = [top]
    for i, row_syms in enumerate(grid):
        row_str = "│  " + "  │  ".join(row_syms) + "  │"
        if payline_index is not None and i == payline_index:
            row_str += "  ⬅️"
        lines.append(row_str)
        if i != len(grid) - 1:
            lines.append(sep)
    lines.append(bottom)
    return "\n".join(lines)


def format_ttt_board(board: str) -> str:
    """نمایش متنی صفحه دوز (برای پیام پایانی، بعد از اینکه دکمه‌ها حذف می‌شوند)."""
    symbols = {".": "➖", "X": "❌", "O": "⭕"}
    rows = []
    for r in range(3):
        cells = [symbols[board[r * 3 + c]] for c in range(3)]
        rows.append(" ".join(cells))
    return "\n".join(rows)


def main_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🎮 Games", callback_data="menu:games")],
        [InlineKeyboardButton("🏙️ City", callback_data="city:menu")],
        [
            InlineKeyboardButton("💰 Balance", callback_data="menu:balance"),
            InlineKeyboardButton("🏦 Exchange", callback_data="menu:exchange"),
        ],
        [
            InlineKeyboardButton("🏆 Leaderboard", callback_data="menu:leaderboard"),
            InlineKeyboardButton("📊 Statistics", callback_data="menu:stats"),
        ],
        [InlineKeyboardButton("❓ Help", callback_data="menu:help")],
    ]
    return InlineKeyboardMarkup(keyboard)


def back_to_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Main Menu", callback_data="menu:main")]])


def games_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🎲 Bet", callback_data="game:bet:info")],
        [
            InlineKeyboardButton("🎲 Dice", callback_data="game:dice:info"),
            InlineKeyboardButton("🔢 Number Guess", callback_data="game:numguess:info"),
        ],
        [
            InlineKeyboardButton("🔤 Word Guess", callback_data="game:wordguess:info"),
            InlineKeyboardButton("✊ Rock Paper Scissors", callback_data="game:rps:info"),
        ],
        [
            InlineKeyboardButton("💎 Survivor", callback_data="game:survivordiamond:info"),
            InlineKeyboardButton("🥇 Survivor Gold", callback_data="game:survivorgold:info"),
        ],
        [
            InlineKeyboardButton("🎰 Slot Machine", callback_data="game:slots:info"),
            InlineKeyboardButton("❌⭕ Tic-Tac-Toe", callback_data="game:tictactoe:info"),
        ],
        [InlineKeyboardButton("⬅️ Main Menu", callback_data="menu:main")],
    ]
    return InlineKeyboardMarkup(keyboard)


def gold_games_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("✊ Rock Paper Scissors", callback_data="game:rps:menu")],
        [InlineKeyboardButton("🥇 Gold Last Survivor", callback_data="game:survivorgold:menu")],
        [InlineKeyboardButton("⬅️ Games", callback_data="menu:games")],
    ]
    return InlineKeyboardMarkup(keyboard)


def diamond_games_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("💎 Last Survivor", callback_data="game:survivordiamond:menu")],
        [InlineKeyboardButton("⬅️ Games", callback_data="menu:games")],
    ]
    return InlineKeyboardMarkup(keyboard)


def balance_text(user_row) -> str:
    games = user_row["games_played"]
    wins = user_row["wins"]
    winrate = (wins / games * 100) if games > 0 else 0.0
    name = user_row["username"] or user_row["display_name"] or str(user_row["user_id"])
    return (
        f"💰 BALANCE — {name}\n\n"
        f"💰 Silver: {fmt_num(user_row['silver'])}\n"
        f"🥇 Gold: {fmt_num(user_row['gold'])}\n"
        f"💎 Diamond: {fmt_num(user_row['diamond'])}\n\n"
        f"━━━━━━━━━━━━\n\n"
        f"🎮 Games: {fmt_num(games)}\n"
        f"🏆 Wins: {fmt_num(wins)}\n"
        f"❌ Losses: {fmt_num(user_row['losses'])}\n"
        f"📈 Win Rate: {winrate:.1f}%"
    )


def stats_text(user_row) -> str:
    games = user_row["games_played"]
    wins = user_row["wins"]
    winrate = (wins / games * 100) if games > 0 else 0.0
    return (
        f"📊 Your Statistics\n\n"
        f"🎮 Total Games: {fmt_num(games)}\n"
        f"🏆 Wins: {fmt_num(wins)}\n"
        f"❌ Losses: {fmt_num(user_row['losses'])}\n"
        f"📈 Win Rate: {winrate:.2f}%\n\n"
        f"💰 Silver Won: {fmt_num(user_row['total_won'])}\n"
        f"💸 Silver Lost: {fmt_num(user_row['total_lost'])}\n\n"
        f"🥇 Gold Won: {fmt_num(user_row['gold_won'])}\n"
        f"💎 Diamond Won: {fmt_num(user_row['diamond_won'])}\n\n"
        f"🎲 Total Bets: {fmt_num(user_row['bets_count'])}"
    )


def profile_text(user_row) -> str:
    import datetime

    games = user_row["games_played"]
    wins = user_row["wins"]
    winrate = (wins / games * 100) if games > 0 else 0.0
    join_date = datetime.datetime.fromtimestamp(user_row["join_date"]).strftime("%Y-%m-%d")
    name = user_row["username"] or user_row["display_name"] or "-"
    return (
        f"👤 Profile\n\n"
        f"Username: {name}\n"
        f"User ID: {user_row['user_id']}\n"
        f"Join Date: {join_date}\n\n"
        f"💰 Silver: {fmt_num(user_row['silver'])}\n"
        f"🥇 Gold: {fmt_num(user_row['gold'])}\n"
        f"💎 Diamond: {fmt_num(user_row['diamond'])}\n\n"
        f"🎮 Games: {fmt_num(games)}\n"
        f"🏆 Wins: {fmt_num(wins)}\n"
        f"❌ Losses: {fmt_num(user_row['losses'])}\n"
        f"📈 Win Rate: {winrate:.1f}%"
    )
