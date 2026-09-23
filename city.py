# -*- coding: utf-8 -*-
"""
city.py
ماژول اقتصاد شهر/زمین/ساختمان — یک Feature کاملاً اضافه (additive) روی ربات فعلی.

این فایل مستقل نگه داشته شده (شبیه games.py که منطق بازی‌ها را جدا نگه می‌دارد)
تا حجم handlers.py غیرقابل مدیریت نشود. از همان singleton مشترک دیتابیس
(database.db) استفاده می‌کند، پس تراکنش‌های City دقیقاً با همان قفل و همان
تضمین Atomic بودن بقیه ربات اجرا می‌شوند.
"""

import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import config
import utils
from database import db

logger = logging.getLogger(__name__)

# کدهای کوتاه برای کاهش حجم callback_data (محدودیت تلگرام: ۶۴ بایت)
TYPE_CODES = {"residential": "res", "commercial": "com", "industrial": "ind", "luxury": "lux", "public": "pub"}
CODE_TYPES = {v: k for k, v in TYPE_CODES.items()}


async def ensure_user(update: Update):
    user = update.effective_user
    row, created = db.get_or_create_user(user.id, user.username or "", user.full_name or "")
    return row, created


def owner_label(user_id: int) -> str:
    u = db.get_user(user_id)
    if u is None:
        return str(user_id)
    return u["username"] or u["display_name"] or str(user_id)


# ==================================================
# منوها
# ==================================================

def city_main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("👤 My City", callback_data="city:mycity")],
            [InlineKeyboardButton("🌆 Public City", callback_data="city:grid:pub")],
            [InlineKeyboardButton("📊 Statistics", callback_data="city:stats")],
            [InlineKeyboardButton("🧾 Taxes", callback_data="city:tax")],
            [InlineKeyboardButton("🏆 City Leaderboards", callback_data="city:lb")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="menu:main")],
        ]
    )


def my_city_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = []
    for t in config.CITY_PERSONAL_TYPES:
        info = config.CITY_TYPE_INFO[t]
        keyboard.append(
            [InlineKeyboardButton(f"{info['emoji']} {info['name']}", callback_data=f"city:grid:{TYPE_CODES[t]}")]
        )
    keyboard.append([InlineKeyboardButton("⬅️ City Menu", callback_data="city:menu")])
    return InlineKeyboardMarkup(keyboard)


async def city_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_user(update)
    text = "🏙️ CITY\n\nManage your personal land, buildings, and compete for Public City plots."
    await update.message.reply_text(text, reply_markup=city_main_menu_keyboard())


# ==================================================
# رسم گرید 10x10
# ==================================================

def cell_label(city_type: str, plot, viewer_id: int) -> str:
    if plot is None:
        return "⬜"
    if city_type == "residential":
        return config.CITY_TYPE_INFO["residential"]["emoji"]
    if city_type == "luxury":
        return config.CITY_TYPE_INFO["luxury"]["emoji"]
    # commercial / industrial / public
    if plot["building_key"]:
        group = "commercial" if city_type == "public" else city_type
        b = db.get_building_def(group, plot["building_key"])
        if b:
            return b["emoji"]
        return "🏗️"
    # بدون Building
    if city_type == "public":
        return "🔷" if plot["owner_id"] == viewer_id else "🔸"
    return "🟫"


def render_grid_text(city_type: str, viewer_id: int) -> str:
    info = config.CITY_TYPE_INFO[city_type]
    if city_type == "public":
        title = "🌆 PUBLIC CITY"
        subtitle = "Shared 10x10 map — compete with everyone for the best zones."
    else:
        title = f"{info['emoji']} {info['name'].upper()}"
        subtitle = "Your personal 10x10 map."
    return f"{title}\n\n{subtitle}\n\nTap any cell to view details."


def grid_keyboard(city_type: str, viewer_id: int) -> InlineKeyboardMarkup:
    if city_type == "public":
        plots_map = db.get_plots_map("public")
    else:
        plots_map = db.get_plots_map(city_type, owner_id=viewer_id)

    size = config.CITY_GRID_SIZE
    rows = []
    for y in range(size):
        row = []
        for x in range(size):
            plot = plots_map.get((x, y))
            label = cell_label(city_type, plot, viewer_id)
            row.append(
                InlineKeyboardButton(label, callback_data=f"city:plot:{TYPE_CODES[city_type]}:{x}:{y}")
            )
        rows.append(row)
    back_target = "city:menu" if city_type == "public" else "city:mycity"
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data=back_target)])
    return InlineKeyboardMarkup(rows)


# ==================================================
# جزئیات یک Plot
# ==================================================

def build_options_keyboard(city_type: str, building_group: str, x: int, y: int) -> InlineKeyboardMarkup:
    buildings = config.CITY_BUILDINGS.get(building_group, {})
    is_public = city_type == "public"
    keyboard = []
    for key, b in sorted(buildings.items(), key=lambda kv: kv[1]["build_cost"]):
        cost = db.compute_build_cost(building_group, key, is_public)
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"{b['emoji']} {b['name']} — {utils.fmt_num(cost)}",
                    callback_data=f"city:build:{TYPE_CODES[city_type]}:{x}:{y}:{key}",
                )
            ]
        )
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data=f"city:plot:{TYPE_CODES[city_type]}:{x}:{y}")])
    return InlineKeyboardMarkup(keyboard)


async def show_plot_detail(query, city_type: str, x: int, y: int, viewer_id: int):
    """پیام و کیبورد جزئیات یک Plot را می‌سازد و ادیت می‌کند."""
    is_public = city_type == "public"
    if is_public:
        plot = db.get_plot("public", x, y)
    else:
        plot = db.get_plot(city_type, x, y, viewer_id)

    # ابتدا Settlement مالک این Plot را (اگر لازم بود) به‌روز کن تا اعداد لحظه‌ای باشند
    if plot is not None:
        db.settle_user_city(plot["owner_id"])
        plot = db.get_plot("public", x, y) if is_public else db.get_plot(city_type, x, y, plot["owner_id"])

    info = config.CITY_TYPE_INFO[city_type]
    plot_code = f"{TYPE_CODES[city_type].upper()}-{x},{y}"

    if plot is None:
        price = db.compute_public_plot_price(x, y) if is_public else db.compute_personal_plot_price(city_type)
        currency = config.PUBLIC_CITY_CURRENCY if is_public else config.CITY_PERSONAL_CURRENCY
        zone_line = ""
        if is_public:
            zone = db.compute_public_zone(x, y)
            zone_line = f"📍 Zone: {zone['name']}\n"
        text = (
            f"🟢 AVAILABLE PLOT\n\n"
            f"📍 Plot: {plot_code}\n"
            f"{info['emoji']} Type: {info['name']}\n"
            f"{zone_line}\n"
            f"💰 Price: {utils.fmt_num(price)} {currency.capitalize()}\n"
        )
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🛒 Buy", callback_data=f"city:buy:{TYPE_CODES[city_type]}:{x}:{y}")],
                [InlineKeyboardButton("⬅️ Back", callback_data=f"city:grid:{TYPE_CODES[city_type]}")],
            ]
        )
        await query.edit_message_text(text, reply_markup=keyboard)
        return

    owner_name = owner_label(plot["owner_id"])
    lines = ["🌆 PUBLIC CITY" if is_public else f"{info['emoji']} {info['name'].upper()} PLOT", ""]
    lines.append(f"📍 Plot: {plot_code}")
    lines.append(f"👤 Owner: {owner_name}")
    lines.append("")

    building_group = "commercial" if is_public else city_type
    if plot["building_key"]:
        b = db.get_building_def(building_group, plot["building_key"])
        value, income, base_rate, _vol = db.compute_building_stats(
            building_group, plot["building_key"], plot["building_level"], is_public
        )
        land_rate = config.CITY_LAND_TAX_RATE.get(city_type, 0.0) if not is_public else 0.0
        est_tax = round(plot["purchase_price"] * land_rate + value * base_rate)
        lines.append(f"{b['emoji']} {b['name']}")
        lines.append(f"⭐ Level {plot['building_level']}/{config.CITY_MAX_BUILDING_LEVEL}")
        lines.append("")
        lines.append(f"💰 Value: {utils.fmt_num(plot['current_value'])}")
        lines.append(f"📈 Income: +{utils.fmt_num(income)}/day (approx.)")
        lines.append(f"🧾 Tax: -{utils.fmt_num(est_tax)}/day (approx., varies daily)")
    else:
        lines.append(f"💰 Value: {utils.fmt_num(plot['current_value'])}")
        if city_type in ("commercial", "industrial", "public"):
            lines.append("🏗️ No building yet — Income: 0/day")
        else:
            land_rate = config.CITY_LAND_TAX_RATE.get(city_type, 0.0)
            if land_rate > 0:
                lines.append(f"🧾 Daily Tax: -{utils.fmt_num(round(plot['current_value'] * land_rate))} (approx.)")

    if plot["tax_debt"] > 0:
        lines.append("")
        lines.append(f"⚠️ Tax Debt: {utils.fmt_num(plot['tax_debt'])}")
        if plot["debt_since"]:
            import time as _time

            days = int((_time.time() - plot["debt_since"]) / 86400)
            lines.append(f"⏳ In debt for {days} day(s) (grace period: {config.CITY_TAX_GRACE_PERIOD_DAYS} days)")

    text = "\n".join(lines)

    keyboard_rows = []
    is_owner = plot["owner_id"] == viewer_id
    if is_owner:
        can_build = city_type in ("commercial", "industrial", "public") and plot["building_key"] is None
        can_upgrade = plot["building_key"] is not None and plot["building_level"] < config.CITY_MAX_BUILDING_LEVEL
        if can_build:
            keyboard_rows.append(
                [InlineKeyboardButton("🏗️ Build", callback_data=f"city:buildmenu:{TYPE_CODES[city_type]}:{x}:{y}")]
            )
        if can_upgrade:
            keyboard_rows.append(
                [InlineKeyboardButton("⬆️ Upgrade", callback_data=f"city:upgrade:{TYPE_CODES[city_type]}:{x}:{y}")]
            )
        keyboard_rows.append(
            [InlineKeyboardButton("🔄 Sell", callback_data=f"city:sell:{TYPE_CODES[city_type]}:{x}:{y}")]
        )
    keyboard_rows.append([InlineKeyboardButton("⬅️ Back", callback_data=f"city:grid:{TYPE_CODES[city_type]}")])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard_rows))


# ==================================================
# Statistics / Tax / Leaderboards
# ==================================================

def city_stats_text(user_id: int) -> str:
    db.settle_user_city(user_id)
    s = db.city_stats_for_user(user_id)
    lines = [
        "🏙️ CITY STATS",
        "",
        f"🏠 Residential Plots: {utils.fmt_num(s['residential'])}",
        f"🏪 Commercial Plots: {utils.fmt_num(s['commercial'])}",
        f"🏭 Industrial Plots: {utils.fmt_num(s['industrial'])}",
        f"💎 Luxury Plots: {utils.fmt_num(s['luxury'])}",
        "",
        f"🏗️ Buildings: {utils.fmt_num(s['buildings'])}",
        "",
        f"📈 Gross Income: +{utils.fmt_num(s['gross_income'])}/day (approx.)",
        f"🧾 Taxes: -{utils.fmt_num(s['taxes'])}/day (approx.)",
        f"💰 Net Income: {utils.fmt_num(s['net_income'])}/day (approx.)",
        "",
        f"📊 Total Property Value: {utils.fmt_num(s['total_value'])}",
        f"⭐ Highest Building Level: {s['highest_level']}",
        f"🌆 Public City Plots: {utils.fmt_num(s['public'])}",
    ]
    return "\n".join(lines)


def city_tax_text(user_id: int) -> str:
    db.settle_user_city(user_id)
    rows = db.get_owned_plots_for_user(user_id)
    in_debt = [p for p in rows if p["tax_debt"] > 0]
    lines = ["🧾 TAXES", ""]
    if not in_debt:
        lines.append("✅ No outstanding tax debt on any of your properties.")
    else:
        lines.append(f"⚠️ {len(in_debt)} propert(y/ies) with outstanding tax debt:")
        lines.append("")
        for p in in_debt:
            info = config.CITY_TYPE_INFO[p["city_type"]]
            lines.append(
                f"{info['emoji']} {TYPE_CODES[p['city_type']].upper()}-{p['x']},{p['y']} — "
                f"Debt: {utils.fmt_num(p['tax_debt'])}"
            )
        lines.append("")
        lines.append(
            f"Properties are never seized for a few days of unpaid tax. Grace period: "
            f"{config.CITY_TAX_GRACE_PERIOD_DAYS} days of continuous debt."
        )
        if config.CITY_DEBT_STOPS_INCOME:
            lines.append("⚠️ Income is paused on indebted properties until the debt is paid off.")
    lines.append("")
    lines.append(f"Taxes are settled automatically every ~{config.CITY_SETTLEMENT_INTERVAL_SECONDS // 3600}h.")
    return "\n".join(lines)


CITY_LB_TITLES = {
    "richest": ("💰 Richest Property Owners", "value"),
    "most_plots": ("🏙️ Most Plots Owned", "plots"),
    "highest_income": ("💰 Highest Daily Income", "per day (approx.)"),
    "highest_level": ("🏗️ Highest Building Level", "level"),
    "public_plots": ("🌆 Biggest Public City Owner", "public plots"),
    "highest_value": ("💎 Highest Property Value", "value"),
}


def city_lb_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = []
    for key, (title, _unit) in CITY_LB_TITLES.items():
        keyboard.append([InlineKeyboardButton(title, callback_data=f"city:lbcat:{key}")])
    keyboard.append([InlineKeyboardButton("⬅️ City Menu", callback_data="city:menu")])
    return InlineKeyboardMarkup(keyboard)


def city_leaderboard_text(category: str) -> str:
    title, unit = CITY_LB_TITLES[category]
    rows = db.city_leaderboard(category, config.CITY_LEADERBOARD_TOP_N)
    lines = [title, ""]
    if not rows:
        lines.append("No data yet.")
    medals = ["👑", "🥈", "🥉"]
    for i, (owner_id, value) in enumerate(rows):
        medal = medals[i] if i < 3 else f"{i + 1}."
        name = owner_label(owner_id)
        lines.append(f"{medal} {name} — {utils.fmt_num(value)} {unit}")
    return "\n".join(lines)


# ==================================================
# Main callback dispatcher
# ==================================================

async def city_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split(":")
    action = parts[1]
    row, _ = await ensure_user(update)
    viewer_id = row["user_id"]

    if action == "menu":
        await query.answer()
        await query.edit_message_text(
            "🏙️ CITY\n\nManage your personal land, buildings, and compete for Public City plots.",
            reply_markup=city_main_menu_keyboard(),
        )

    elif action == "mycity":
        await query.answer()
        await query.edit_message_text("👤 MY CITY\n\nChoose a map:", reply_markup=my_city_menu_keyboard())

    elif action == "grid":
        code = parts[2]
        city_type = CODE_TYPES[code]
        if city_type != "public":
            db.settle_user_city(viewer_id)
        await query.answer()
        await query.edit_message_text(
            render_grid_text(city_type, viewer_id), reply_markup=grid_keyboard(city_type, viewer_id)
        )

    elif action == "plot":
        code, x, y = parts[2], int(parts[3]), int(parts[4])
        city_type = CODE_TYPES[code]
        await query.answer()
        await show_plot_detail(query, city_type, x, y, viewer_id)

    elif action == "buy":
        code, x, y = parts[2], int(parts[3]), int(parts[4])
        city_type = CODE_TYPES[code]
        if city_type == "public":
            success, msg, plot = db.buy_public_plot(viewer_id, x, y)
        else:
            success, msg, plot = db.buy_personal_plot(viewer_id, city_type, x, y)
        if not success:
            await query.answer(msg, show_alert=True)
            # صفحه را رفرش کن تا اگر توسط دیگری خریداری شده، وضعیت واقعی نشان داده شود
            await show_plot_detail(query, city_type, x, y, viewer_id)
            return
        await query.answer("✅ Purchased!")
        await show_plot_detail(query, city_type, x, y, viewer_id)

    elif action == "buildmenu":
        code, x, y = parts[2], int(parts[3]), int(parts[4])
        city_type = CODE_TYPES[code]
        building_group = "commercial" if city_type == "public" else city_type
        await query.answer()
        await query.edit_message_text(
            "🏗️ Choose a building to construct:",
            reply_markup=build_options_keyboard(city_type, building_group, x, y),
        )

    elif action == "build":
        code, x, y, building_key = parts[2], int(parts[3]), int(parts[4]), parts[5]
        city_type = CODE_TYPES[code]
        if city_type == "public":
            success, msg, plot = _build_public(viewer_id, x, y, building_key)
        else:
            success, msg, plot = db.build_building(viewer_id, city_type, x, y, building_key)
        if not success:
            await query.answer(msg, show_alert=True)
            return
        await query.answer("✅ Built!")
        await show_plot_detail(query, city_type, x, y, viewer_id)

    elif action == "upgrade":
        code, x, y = parts[2], int(parts[3]), int(parts[4])
        city_type = CODE_TYPES[code]
        if city_type == "public":
            success, msg, plot = _upgrade_public(viewer_id, x, y)
        else:
            success, msg, plot = db.upgrade_building(viewer_id, city_type, x, y)
        if not success:
            await query.answer(msg, show_alert=True)
            return
        await query.answer("✅ Upgraded!")
        await show_plot_detail(query, city_type, x, y, viewer_id)

    elif action == "sell":
        code, x, y = parts[2], int(parts[3]), int(parts[4])
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ Confirm Sell", callback_data=f"city:sellok:{code}:{x}:{y}")],
                [InlineKeyboardButton("❌ Cancel", callback_data=f"city:plot:{code}:{x}:{y}")],
            ]
        )
        sell_pct = int(config.CITY_SELL_PERCENTAGE * 100)
        await query.answer()
        await query.edit_message_text(
            f"🔄 Are you sure you want to sell this plot?\n\nYou'll get back {sell_pct}% of its current value.",
            reply_markup=keyboard,
        )

    elif action == "sellok":
        code, x, y = parts[2], int(parts[3]), int(parts[4])
        city_type = CODE_TYPES[code]
        success, msg, refund = db.sell_plot(viewer_id, city_type, x, y)
        if not success:
            await query.answer(msg, show_alert=True)
            return
        currency = config.PUBLIC_CITY_CURRENCY if city_type == "public" else config.CITY_PERSONAL_CURRENCY
        await query.answer(f"Sold for {refund} {currency.capitalize()}.")
        await query.edit_message_text(
            f"✅ Plot sold for {utils.fmt_num(refund)} {currency.capitalize()}.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅️ Back to Map", callback_data=f"city:grid:{code}")]]
            ),
        )

    elif action == "stats":
        await query.answer()
        await query.edit_message_text(
            city_stats_text(viewer_id),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ City Menu", callback_data="city:menu")]]),
        )

    elif action == "tax":
        await query.answer()
        await query.edit_message_text(
            city_tax_text(viewer_id),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ City Menu", callback_data="city:menu")]]),
        )

    elif action == "lb":
        await query.answer()
        await query.edit_message_text("🏆 City Leaderboards\n\nChoose a category:", reply_markup=city_lb_menu_keyboard())

    elif action == "lbcat":
        category = parts[2]
        await query.answer()
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("⬅️ Leaderboards", callback_data="city:lb")],
                [InlineKeyboardButton("🏠 City Menu", callback_data="city:menu")],
            ]
        )
        await query.edit_message_text(city_leaderboard_text(category), reply_markup=keyboard)


def _build_public(user_id, x, y, building_key):
    """
    Public City از همان تعریف Buildingهای Commercial استفاده می‌کند، اما با ضرایب بالاتر
    (Build Cost / Income / Value). منطق مشابه database.build_building است ولی روی
    Plotهای city_type='public' کار می‌کند، پس اینجا (نه در database.py) نگه داشته شده
    تا build_building عادی برای شهر شخصی دست‌نخورده و ساده بماند.
    """
    b = db.get_building_def("commercial", building_key)
    if b is None:
        return False, "❌ Unknown building type.", None
    cost = db.compute_build_cost("commercial", building_key, True)
    currency = config.PUBLIC_CITY_CURRENCY
    try:
        with db.transaction() as conn:
            plot = conn.execute(
                "SELECT * FROM plots WHERE city_type = 'public' AND owner_id = ? AND x = ? AND y = ?",
                (user_id, x, y),
            ).fetchone()
            if plot is None:
                raise ValueError("not_owned")
            if plot["building_key"] is not None:
                raise ValueError("already_built")
            row = conn.execute(f"SELECT {currency} FROM users WHERE user_id = ?", (user_id,)).fetchone()
            if row is None or row[currency] < cost:
                raise ValueError("insufficient")
            db.adjust_balance(conn, user_id, currency, -cost)
            value, _income, _rate, _vol = db.compute_building_stats("commercial", building_key, 1, True)
            new_value = plot["purchase_price"] + value
            conn.execute(
                "UPDATE plots SET building_key = ?, building_level = 1, current_value = ? WHERE plot_id = ?",
                (building_key, new_value, plot["plot_id"]),
            )
    except ValueError as e:
        reason = str(e)
        if reason == "not_owned":
            return False, "❌ You don't own this plot.", None
        if reason == "already_built":
            return False, "❌ This plot already has a building.", None
        return False, f"❌ You don't have enough {currency.capitalize()}.", None
    return True, "ok", db.get_plot("public", x, y)


def _upgrade_public(user_id, x, y):
    currency = config.PUBLIC_CITY_CURRENCY
    try:
        with db.transaction() as conn:
            plot = conn.execute(
                "SELECT * FROM plots WHERE city_type = 'public' AND owner_id = ? AND x = ? AND y = ?",
                (user_id, x, y),
            ).fetchone()
            if plot is None:
                raise ValueError("not_owned")
            if plot["building_key"] is None:
                raise ValueError("no_building")
            if plot["building_level"] >= config.CITY_MAX_BUILDING_LEVEL:
                raise ValueError("max_level")
            cost = db.compute_upgrade_cost("commercial", plot["building_key"], plot["building_level"], True)
            row = conn.execute(f"SELECT {currency} FROM users WHERE user_id = ?", (user_id,)).fetchone()
            if row is None or row[currency] < cost:
                raise ValueError("insufficient")
            db.adjust_balance(conn, user_id, currency, -cost)
            new_level = plot["building_level"] + 1
            value, _income, _rate, _vol = db.compute_building_stats(
                "commercial", plot["building_key"], new_level, True
            )
            new_value = plot["purchase_price"] + value
            conn.execute(
                "UPDATE plots SET building_level = ?, current_value = ? WHERE plot_id = ?",
                (new_level, new_value, plot["plot_id"]),
            )
    except ValueError as e:
        reason = str(e)
        if reason == "not_owned":
            return False, "❌ You don't own this plot.", None
        if reason == "no_building":
            return False, "❌ Build something here first.", None
        if reason == "max_level":
            return False, "❌ This building is already at max level.", None
        return False, f"❌ You don't have enough {currency.capitalize()}.", None
    return True, "ok", db.get_plot("public", x, y)


# ==================================================
# Background job: Settlement خودکار
# ==================================================

async def city_settlement_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        count = db.settle_all_plots()
        if count:
            logger.info("City settlement job processed %d plot(s).", count)
    except Exception:
        logger.exception("City settlement job failed")
