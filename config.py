# -*- coding: utf-8 -*-
"""
Config.py
همه تنظیمات مهم پروژه اینجا هستند تا لازم نباشد در چند جای کد مقدار چیزی را تغییر دهید.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ==================================================
# توکن ربات و ادمین
# ==================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# آیدی عددی تلگرام ادمین (نه Username!). برای گرفتن آیدی خودتان می‌توانید
# به @userinfobot در تلگرام پیام بدهید.
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

DATABASE_PATH = os.getenv("DATABASE_PATH", "bot_database.db")

# ==================================================
# پراکسی (اختیاری)
# اگر در منطقه‌ای هستید که اتصال مستقیم به تلگرام ناپایدار یا فیلتر است،
# می‌توانید آدرس پراکسی خودتان را اینجا (از طریق .env) تنظیم کنید.
# مثال مقدار: http://127.0.0.1:10809  یا  socks5://127.0.0.1:1080
# اگر خالی بماند، هیچ پراکسی‌ای استفاده نمی‌شود.
# ==================================================

PROXY_URL = os.getenv("PROXY_URL", "").strip()

# ==================================================
# موجودی اولیه کاربر جدید
# ==================================================

STARTING_SILVER = 100
STARTING_GOLD = 0
STARTING_DIAMOND = 0

# ==================================================
# سیستم /gain (جایزه روزانه)
# ==================================================

GAIN_COOLDOWN_HOURS = 24
GAIN_MIN_AMOUNT = 1
GAIN_MAX_AMOUNT = 100

# ==================================================
# نرخ تبدیل Exchange
# این مقادیر یعنی: چند Silver لازم است تا 1 واحد از ارز مقصد ساخته شود.
# ==================================================

EXCHANGE_RATES = {
    "silver_to_gold": 100,     # 100 Silver -> 1 Gold
    "silver_to_diamond": 1000,  # 1000 Silver -> 1 Diamond
}

# حداقل مقدار Silver قابل تبدیل در هر تراکنش Exchange (باید مضربی از نرخ باشد)
EXCHANGE_MIN_SILVER = 100

# ==================================================
# محدودیت‌های Bet
# ==================================================

BET_MIN_AMOUNT = 1
BET_MAX_AMOUNT = 100000

# بعد از چند دقیقه یک Bet بدون حریف منقضی می‌شود
BET_EXPIRE_MINUTES = 60

# ==================================================
# بازی Dice
# ==================================================

DICE_MIN_BET = 1
DICE_MAX_BET = 100000
# ضریب جایزه حدس زوج/فرد
DICE_EVEN_ODD_MULTIPLIER = 2
# ضریب جایزه حدس عدد دقیق (1 تا 6)
DICE_EXACT_MULTIPLIER = 6

# ==================================================
# بازی Number Guess
# هر بازه یک ضریب جایزه متفاوت دارد (هرچه بازه بزرگ‌تر، جایزه بیشتر)
# ==================================================

NUMBER_GUESS_RANGES = {
    "5": {"max": 5, "multiplier": 3},
    "10": {"max": 10, "multiplier": 5},
    "20": {"max": 20, "multiplier": 10},
    "50": {"max": 50, "multiplier": 25},
}
NUMBER_GUESS_MIN_BET = 1
NUMBER_GUESS_MAX_BET = 100000

# ==================================================
# بازی Word Guess
# ==================================================

WORD_GUESS_REWARDS = {
    "easy": 10,
    "medium": 25,
    "hard": 60,
}
WORD_GUESS_BET = 5  # مقداری که از کاربر برای شرکت در بازی کم می‌شود (صرف نظر از نتیجه)

WORD_GUESS_BANK = {
    "easy": [
        {"word": "SUN", "options": ["SUN", "MOON", "STAR", "SKY"]},
        {"word": "CAT", "options": ["CAT", "DOG", "BIRD", "FISH"]},
        {"word": "BOOK", "options": ["BOOK", "PEN", "DESK", "CHAIR"]},
        {"word": "APPLE", "options": ["APPLE", "GRAPE", "MANGO", "LEMON"]},
    ],
    "medium": [
        {"word": "GUITAR", "options": ["GUITAR", "VIOLIN", "PIANO", "DRUMS"]},
        {"word": "MOUNTAIN", "options": ["MOUNTAIN", "RIVER", "OCEAN", "DESERT"]},
        {"word": "ELEPHANT", "options": ["ELEPHANT", "TIGER", "ZEBRA", "GIRAFFE"]},
        {"word": "LIBRARY", "options": ["LIBRARY", "MUSEUM", "SCHOOL", "MARKET"]},
    ],
    "hard": [
        {"word": "PHILOSOPHY", "options": ["PHILOSOPHY", "PSYCHOLOGY", "GEOLOGY", "ASTRONOMY"]},
        {"word": "REFRIGERATOR", "options": ["REFRIGERATOR", "MICROWAVE", "DISHWASHER", "BLENDER"]},
        {"word": "ARCHITECTURE", "options": ["ARCHITECTURE", "ENGINEERING", "MEDICINE", "CHEMISTRY"]},
        {"word": "ENTREPRENEUR", "options": ["ENTREPRENEUR", "ACCOUNTANT", "TECHNICIAN", "SCIENTIST"]},
    ],
}

# ==================================================
# Rock Paper Scissors (Gold)
# ==================================================

RPS_MIN_BET = 1
RPS_MAX_BET = 100000
RPS_JOIN_TIMEOUT_MINUTES = 15
# تعداد راند بردی که برای بردن کل مسابقه لازم است (2 = Best of 3، اولین کسی که 2 راند ببرد برنده کل است)
RPS_ROUNDS_TO_WIN = 2

# ==================================================
# Slot Machine
# ==================================================

SLOTS_MIN_BET = 1
SLOTS_MAX_BET = 100000
SLOTS_ROWS = 3
SLOTS_COLS = 3

# هر نماد و وزن نسبی آن در قرعه‌کشی (عدد بزرگ‌تر یعنی احتمال بیشتر آمدن آن نماد)
SLOTS_SYMBOLS = {
    "🍒": 30,
    "🍋": 25,
    "🍊": 20,
    "🔔": 15,
    "⭐": 7,
    "7️⃣": 2,
    "💎": 1,
}

# ضریب پرداخت بر اساس خط وسط (payline). این مقادیر در سود بازیکن ضرب می‌شوند.
SLOTS_PAYOUTS = {
    "three_of_a_kind": {
        "default": 5,   # سه نماد یکسان معمولی
        "7️⃣": 20,       # سه عدد 7 -> جایزه ویژه
        "💎": 50,        # سه Diamond -> جایزه ویژه
    },
    "two_of_a_kind": 1.5,  # دو نماد یکسان (هر نمادی) -> جایزه کوچک‌تر
}

# ==================================================
# Tic-Tac-Toe (دوز)
# ==================================================
# این بازی جایزه/شرط ندارد؛ فقط برای سرگرمی است و در آمار/Leaderboard (تعداد بازی، برد، باخت) ثبت می‌شود.

# ==================================================
# Last Survivor (Diamond) - بازی حذفی چند نفره
# ==================================================

SURVIVOR_DIAMOND_MIN_PLAYERS = 2
SURVIVOR_DIAMOND_MAX_PLAYERS = 6
SURVIVOR_DIAMOND_MIN_STAKE = 1
SURVIVOR_DIAMOND_MAX_STAKE = 100000
SURVIVOR_DIAMOND_ROUND_DELAY_SECONDS = 2  # فاصله بین هر مرحله حذف برای ساسپنس
SURVIVOR_LOBBY_TIMEOUT_MINUTES = 20

# ==================================================
# Gold Last Survivor - نسخه کوچک‌تر
# ==================================================

SURVIVOR_GOLD_MIN_PLAYERS = 2
SURVIVOR_GOLD_MAX_PLAYERS = 3
SURVIVOR_GOLD_MIN_STAKE = 1
SURVIVOR_GOLD_MAX_STAKE = 100000
SURVIVOR_GOLD_ROUND_DELAY_SECONDS = 2
SURVIVOR_GOLD_LOBBY_TIMEOUT_MINUTES = 20

# ==================================================
# فعال/غیرفعال بودن بازی‌ها (توسط ادمین قابل تغییر - در دیتابیس ذخیره می‌شود)
# این فقط مقدار پیش‌فرض اولیه است.
# ==================================================

DEFAULT_GAME_STATUS = {
    "dice": True,
    "number_guess": True,
    "word_guess": True,
    "bet": True,
    "rps": True,
    "survivor_diamond": True,
    "survivor_gold": True,
    "slots": True,
    "tictactoe": True,
}

# ==================================================
# Leaderboard
# ==================================================

LEADERBOARD_TOP_N = 10

# ======================================================================
# 🏙️ CITY / LAND / PROPERTY ECONOMY
# این بخش کاملاً اضافه (additive) است و به Currencyهای فعلی (Silver/Gold/Diamond)
# متصل می‌شود. Gold در این سیستم استفاده نمی‌شود (طبق طراحی: Silver برای اقتصاد
# روزمره شهر شخصی، Diamond فقط برای Public City).
# ======================================================================

CITY_GRID_SIZE = 10  # هر Map یک 10x10 است (مختصات 0 تا 9)

# چهار نوع زمین شخصی. هر کاربر یک Grid کامل و مستقل از هرکدام دارد.
CITY_PERSONAL_TYPES = ["residential", "commercial", "industrial", "luxury"]

CITY_TYPE_INFO = {
    "residential": {"emoji": "🏠", "name": "Residential"},
    "commercial": {"emoji": "🏪", "name": "Commercial"},
    "industrial": {"emoji": "🏭", "name": "Industrial"},
    "luxury": {"emoji": "💎", "name": "Luxury"},
    "public": {"emoji": "🌆", "name": "Public City"},
}

# ارزی که برای خرید/ساخت/ارتقا در هر نوع زمین استفاده می‌شود
CITY_PERSONAL_CURRENCY = "silver"
PUBLIC_CITY_CURRENCY = "diamond"

# قیمت پایه خرید هر Plot خالی در شهر شخصی (Silver)
CITY_PLOT_BASE_PRICE = {
    "residential": 150,
    "commercial": 500,
    "industrial": 800,
    "luxury": 3000,
}

# نرخ مالیات روزانه‌ای که فقط بر اساس "ارزش زمین" (نه ساختمان) محاسبه می‌شود.
# Residential فعلاً بدون مالیات است (فقط مالکیت/ارزش، برای توسعه آینده).
# Luxury عمداً بسیار بالاتر از بقیه است.
CITY_LAND_TAX_RATE = {
    "residential": 0.0,
    "commercial": 0.006,
    "industrial": 0.007,
    "luxury": 0.02,
}

# ------------------------------------------------
# Buildings (فقط Commercial و Industrial قابل Build/Upgrade هستند)
# هر Building یک منحنی رشد دارد: هر Level نسبت به Level قبل با ضریب رشد افزایش می‌یابد.
# Building ارزان‌تر => base_tax_rate کمتر ولی tax_volatility (نوسان) بیشتر.
# Building گران‌تر  => base_tax_rate بیشتر ولی tax_volatility کمتر (پایدارتر).
# ------------------------------------------------

CITY_MAX_BUILDING_LEVEL = 10

CITY_BUILDINGS = {
    "commercial": {
        "small_shop": {
            "emoji": "🛒", "name": "Small Shop",
            "build_cost": 200, "base_value": 250, "value_growth": 1.25,
            "base_income": 30, "income_growth": 1.30,
            "upgrade_cost_base": 150, "upgrade_cost_growth": 1.35,
            "base_tax_rate": 0.012, "tax_volatility": 0.60,
        },
        "grocery_store": {
            "emoji": "🏪", "name": "Grocery Store",
            "build_cost": 500, "base_value": 600, "value_growth": 1.25,
            "base_income": 70, "income_growth": 1.30,
            "upgrade_cost_base": 350, "upgrade_cost_growth": 1.35,
            "base_tax_rate": 0.016, "tax_volatility": 0.45,
        },
        "restaurant": {
            "emoji": "🍔", "name": "Restaurant",
            "build_cost": 1000, "base_value": 1200, "value_growth": 1.22,
            "base_income": 150, "income_growth": 1.28,
            "upgrade_cost_base": 700, "upgrade_cost_growth": 1.32,
            "base_tax_rate": 0.020, "tax_volatility": 0.35,
        },
        "supermarket": {
            "emoji": "🏬", "name": "Supermarket",
            "build_cost": 2500, "base_value": 3000, "value_growth": 1.20,
            "base_income": 320, "income_growth": 1.26,
            "upgrade_cost_base": 1600, "upgrade_cost_growth": 1.30,
            "base_tax_rate": 0.024, "tax_volatility": 0.25,
        },
        "business_center": {
            "emoji": "🏢", "name": "Business Center",
            "build_cost": 6000, "base_value": 7000, "value_growth": 1.18,
            "base_income": 650, "income_growth": 1.24,
            "upgrade_cost_base": 3500, "upgrade_cost_growth": 1.28,
            "base_tax_rate": 0.028, "tax_volatility": 0.18,
        },
        "shopping_mall": {
            "emoji": "🏙️", "name": "Shopping Mall",
            "build_cost": 15000, "base_value": 18000, "value_growth": 1.16,
            "base_income": 1400, "income_growth": 1.22,
            "upgrade_cost_base": 8000, "upgrade_cost_growth": 1.25,
            "base_tax_rate": 0.032, "tax_volatility": 0.12,
        },
        "luxury_mall": {
            "emoji": "💎", "name": "Luxury Mall",
            "build_cost": 35000, "base_value": 42000, "value_growth": 1.14,
            "base_income": 3000, "income_growth": 1.20,
            "upgrade_cost_base": 18000, "upgrade_cost_growth": 1.22,
            "base_tax_rate": 0.036, "tax_volatility": 0.08,
        },
    },
    "industrial": {
        "factory": {
            "emoji": "🏭", "name": "Factory",
            "build_cost": 1500, "base_value": 1800, "value_growth": 1.25,
            "base_income": 200, "income_growth": 1.30,
            "upgrade_cost_base": 900, "upgrade_cost_growth": 1.30,
            "base_tax_rate": 0.020, "tax_volatility": 0.30,
        },
    },
}

# کف/سقف مطلق نرخ مالیات روزانه (فارغ از تنظیمات هر Building) — هیچ نرخی
# هرگز از این محدوده خارج نمی‌شود، حتی با تنظیمات نادرست در config.
CITY_TAX_RATE_ABS_MIN = 0.001
CITY_TAX_RATE_ABS_MAX = 0.08

# ------------------------------------------------
# Settlement (محاسبه خودکار Income/Tax)
# ------------------------------------------------

# طول هر "روز اقتصادی" شهر برای محاسبه Income/Tax (بر حسب ثانیه). 86400 = ۲۴ ساعت واقعی.
CITY_SETTLEMENT_INTERVAL_SECONDS = 86400

# اگر بات مدت زیادی Offline بود، حداکثر چند دوره Settlement پشت‌سرهم برای یک Plot
# محاسبه می‌شود (برای جلوگیری از اعداد نجومی بعد از خاموشی طولانی).
CITY_MAX_CATCHUP_PERIODS = 30

# فاصله زمانی اجرای Job پس‌زمینه‌ای که همه Plotها را برای Settlement بررسی می‌کند (ثانیه)
CITY_SETTLEMENT_JOB_INTERVAL_SECONDS = 1800  # هر 30 دقیقه

# ------------------------------------------------
# Tax Debt / Grace Period
# ------------------------------------------------

# اگر Plot بدهی مالیاتی داشته باشد، آیا تا زمان پرداخت بدهی، Income آن متوقف شود؟
CITY_DEBT_STOPS_INCOME = True

# چند روز بدهی مالیاتی مداوم مجاز است قبل از این‌که Property واجد شرایط
# Auction/Seizure در آینده شود (خود عملیات Seizure در این نسخه پیاده‌سازی نشده،
# فقط وضعیت/هشدار آن ثبت و نمایش داده می‌شود).
CITY_TAX_GRACE_PERIOD_DAYS = 14

# ------------------------------------------------
# فروش Property (Marketplace پایه)
# ------------------------------------------------

# درصدی از current_value که هنگام فروش به سیستم به کاربر برگردانده می‌شود
CITY_SELL_PERCENTAGE = 0.60

# ------------------------------------------------
# Public City
# ------------------------------------------------

PUBLIC_CITY_BASE_PRICE = 700  # حداقل قیمت هر Plot در Outer Zone (Diamond)

# Zoneها بر اساس فاصله (Chebyshev) از مرکز Grid (4.5, 4.5) تعیین می‌شوند.
# اولین Zone ای که فاصله Plot از مرکز <= max_distance آن باشد استفاده می‌شود؛
# لیست باید از نزدیک‌ترین (کوچک‌ترین max_distance) به دورترین مرتب باشد.
PUBLIC_CITY_ZONES = [
    {"name": "Center", "max_distance": 1.5, "multiplier": 2.2},
    {"name": "Inner", "max_distance": 2.5, "multiplier": 1.5},
    {"name": "Middle", "max_distance": 3.5, "multiplier": 1.2},
    {"name": "Outer", "max_distance": 99, "multiplier": 1.0},
]

# در Public City، هزینه ساخت و درآمد Buildingهای Commercial (همان لیست بالا،
# بدون تکرار تعریف) در این ضرایب ضرب می‌شود => "High Cost = High Income".
PUBLIC_CITY_BUILD_COST_MULTIPLIER = 3.0
PUBLIC_CITY_INCOME_MULTIPLIER = 4.0
PUBLIC_CITY_VALUE_MULTIPLIER = 3.0

# ------------------------------------------------
# City Leaderboards
# ------------------------------------------------

CITY_LEADERBOARD_TOP_N = 10
