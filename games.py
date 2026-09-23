# -*- coding: utf-8 -*-
"""
games.py
منطق خالص بازی‌ها (بدون وابستگی به تلگرام). هندلرها این توابع را صدا می‌زنند.
"""

import random
import config


def roll_dice() -> int:
    return random.randint(1, 6)


def dice_even_odd_result(guess: str, rolled: int) -> bool:
    """guess: 'even' یا 'odd'"""
    is_even = rolled % 2 == 0
    return (guess == "even") == is_even


def dice_exact_result(guess: int, rolled: int) -> bool:
    return guess == rolled


def number_guess_pick(max_value: int) -> int:
    return random.randint(1, max_value)


def rps_winner(choice1: str, choice2: str):
    """
    برمی‌گرداند: 1 اگر بازیکن اول برنده باشد، 2 اگر دوم، 0 اگر مساوی.
    choice: 'rock' | 'paper' | 'scissors'
    """
    if choice1 == choice2:
        return 0
    beats = {"rock": "scissors", "paper": "rock", "scissors": "paper"}
    if beats[choice1] == choice2:
        return 1
    return 2


def eliminate_order(player_ids: list) -> list:
    """
    ترتیب حذف بازیکنان را تصادفی برمی‌گرداند.
    خروجی لیستی از player_id هاست، از اولین‌کسی که حذف می‌شود تا برنده نهایی (آخرین عضو لیست).
    """
    shuffled = player_ids[:]
    random.shuffle(shuffled)
    return shuffled  # shuffled[0] اول حذف می‌شود ... shuffled[-1] برنده است


def pick_word(difficulty: str):
    bank = config.WORD_GUESS_BANK.get(difficulty)
    if not bank:
        return None
    entry = random.choice(bank)
    options = entry["options"][:]
    random.shuffle(options)
    return {"word": entry["word"], "options": options}


# ==================================================
# Slot Machine
# ==================================================

def spin_slots(rows: int, cols: int):
    """یک شبکه rows x cols از نمادها را بر اساس وزن‌های config می‌سازد."""
    symbols = list(config.SLOTS_SYMBOLS.keys())
    weights = list(config.SLOTS_SYMBOLS.values())
    return [random.choices(symbols, weights=weights, k=cols) for _ in range(rows)]


def evaluate_slots_payline(payline: list):
    """
    payline: لیست نمادهای خط وسط (payline).
    خروجی: (multiplier: float, kind: str)
    kind یکی از 'three_of_a_kind' | 'two_of_a_kind' | 'none' است.
    """
    if payline[0] == payline[1] == payline[2]:
        symbol = payline[0]
        table = config.SLOTS_PAYOUTS["three_of_a_kind"]
        multiplier = table.get(symbol, table["default"])
        return multiplier, "three_of_a_kind"
    if payline[0] == payline[1] or payline[1] == payline[2] or payline[0] == payline[2]:
        return config.SLOTS_PAYOUTS["two_of_a_kind"], "two_of_a_kind"
    return 0, "none"


# ==================================================
# Tic-Tac-Toe
# ==================================================

TTT_WIN_LINES = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),  # ردیف‌ها
    (0, 3, 6), (1, 4, 7), (2, 5, 8),  # ستون‌ها
    (0, 4, 8), (2, 4, 6),             # قطرها
]


def check_ttt_winner(board: str):
    """
    board: رشته ۹ کاراکتری شامل '.', 'X', 'O' (خانه‌های خالی '.').
    اگر خطی برنده وجود داشته باشد 'X' یا 'O' برمی‌گرداند، وگرنه None.
    """
    for a, b, c in TTT_WIN_LINES:
        if board[a] != "." and board[a] == board[b] == board[c]:
            return board[a]
    return None
