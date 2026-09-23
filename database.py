# -*- coding: utf-8 -*-
"""
database.py
تمام دسترسی‌ها به SQLite از اینجا انجام می‌شود.

نکته امنیتی مهم:
تمام عملیاتی که موجودی کاربران را تغییر می‌دهند (Bet, Games, Exchange, Admin)
باید از طریق متدهای این فایل و داخل یک تراکنش (transaction) انجام شوند تا از
Double Spending یا خراب شدن دیتا در اثر اجرای همزمان جلوگیری شود.
علاوه بر تراکنش دیتابیس، در سطح برنامه هم از asyncio.Lock در handlers.py
برای بخش‌های حساس (مثل Join Bet) استفاده می‌شود.
"""

import sqlite3
import time
import random
import threading
from contextlib import contextmanager

import config
import games


class Database:
    def __init__(self, path: str = None):
        self.path = path or config.DATABASE_PATH
        # یک لاک سطح پایتون برای هماهنگی نوشتن‌های همزمان (SQLite خودش هم قفل دارد،
        # اما این لاک از تداخل منطقی بین چند عملیات چندمرحله‌ای جلوگیری می‌کند)
        self._lock = threading.Lock()
        self._local = threading.local()
        self._init_db()

    # ------------------------------------------------
    # اتصال
    # ------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        """هر Thread کانکشن مخصوص خودش را دارد (چون sqlite3 به‌صورت پیش‌فرض thread-safe نیست)."""
        if not hasattr(self._local, "conn"):
            conn = sqlite3.connect(self.path, timeout=30)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            self._local.conn = conn
        return self._local.conn

    @contextmanager
    def transaction(self):
        """
        یک context manager برای تراکنش‌های امن.
        در صورت بروز خطا، تغییرات Rollback می‌شوند.
        """
        conn = self._get_conn()
        with self._lock:
            try:
                conn.execute("BEGIN IMMEDIATE")
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                display_name TEXT,
                silver INTEGER NOT NULL DEFAULT 0,
                gold INTEGER NOT NULL DEFAULT 0,
                diamond INTEGER NOT NULL DEFAULT 0,
                games_played INTEGER NOT NULL DEFAULT 0,
                wins INTEGER NOT NULL DEFAULT 0,
                losses INTEGER NOT NULL DEFAULT 0,
                bets_count INTEGER NOT NULL DEFAULT 0,
                total_won INTEGER NOT NULL DEFAULT 0,
                total_lost INTEGER NOT NULL DEFAULT 0,
                gold_won INTEGER NOT NULL DEFAULT 0,
                diamond_won INTEGER NOT NULL DEFAULT 0,
                last_gain REAL,
                join_date REAL NOT NULL,
                is_banned INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS bets (
                bet_id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id INTEGER NOT NULL,
                opponent_id INTEGER,
                stake INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',  -- open, closed, cancelled, expired
                winner_id INTEGER,
                chat_id INTEGER,
                message_id INTEGER,
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS lobbies (
                lobby_id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_type TEXT NOT NULL,   -- rps, survivor_diamond, survivor_gold
                creator_id INTEGER NOT NULL,
                stake INTEGER NOT NULL,
                currency TEXT NOT NULL,
                max_players INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'open', -- open, started, finished, cancelled
                chat_id INTEGER,
                message_id INTEGER,
                winner_id INTEGER,
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS lobby_players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lobby_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                choice TEXT,
                joined_at REAL NOT NULL,
                UNIQUE(lobby_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS admin_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                target_user_id INTEGER,
                amount INTEGER,
                currency TEXT,
                note TEXT,
                timestamp REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS game_status (
                game_key TEXT PRIMARY KEY,
                enabled INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS ttt_games (
                game_id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_x INTEGER NOT NULL,
                player_o INTEGER,
                board TEXT NOT NULL DEFAULT '.........',
                turn TEXT NOT NULL DEFAULT 'X',
                status TEXT NOT NULL DEFAULT 'open',  -- open, active, finished, cancelled
                winner_id INTEGER,
                chat_id INTEGER,
                message_id INTEGER,
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS plots (
                plot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                city_type TEXT NOT NULL,       -- residential, commercial, industrial, luxury, public
                owner_id INTEGER NOT NULL,     -- شهر شخصی: همیشه = صاحب آن شهر. Public: خریدار.
                x INTEGER NOT NULL,
                y INTEGER NOT NULL,
                purchase_price INTEGER NOT NULL,
                current_value INTEGER NOT NULL,
                building_key TEXT,             -- کلید Building در config.CITY_BUILDINGS، یا NULL
                building_level INTEGER NOT NULL DEFAULT 0,
                tax_debt INTEGER NOT NULL DEFAULT 0,
                debt_since REAL,               -- زمان شروع بدهی مداوم (برای Grace Period)، یا NULL
                last_settlement REAL NOT NULL,
                created_at REAL NOT NULL
            );

            -- شهر شخصی: هر کاربر برای هر (city_type, x, y) فقط یک بار می‌تواند Plot داشته باشد
            CREATE UNIQUE INDEX IF NOT EXISTS ux_plots_personal
                ON plots(city_type, owner_id, x, y) WHERE city_type != 'public';

            -- Public City: هر (x, y) در کل ربات فقط یک مالک دارد (این ایندکس همان چیزی
            -- است که خرید هم‌زمان یک Plot توسط دو کاربر را در سطح دیتابیس غیرممکن می‌کند)
            CREATE UNIQUE INDEX IF NOT EXISTS ux_plots_public
                ON plots(x, y) WHERE city_type = 'public';
            """
        )
        conn.commit()

        # ------------------------------------------------
        # Migration امن: اگر از نسخه قبلی آپدیت می‌کنید، این ستون‌های جدید
        # (لازم برای Rock Paper Scissors چند راندی) بدون از دست رفتن داده‌های
        # قبلی به جدول lobbies اضافه می‌شوند.
        # ------------------------------------------------
        self._ensure_column(conn, "lobbies", "rps_round", "INTEGER NOT NULL DEFAULT 1")
        self._ensure_column(conn, "lobbies", "rps_score_creator", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column(conn, "lobbies", "rps_score_opponent", "INTEGER NOT NULL DEFAULT 0")
        conn.commit()

        # مقداردهی اولیه وضعیت بازی‌ها در صورتی که هنوز وجود ندارند
        for key, enabled in config.DEFAULT_GAME_STATUS.items():
            conn.execute(
                "INSERT OR IGNORE INTO game_status (game_key, enabled) VALUES (?, ?)",
                (key, 1 if enabled else 0),
            )
        conn.commit()

    def _ensure_column(self, conn, table: str, column: str, coldef: str):
        """اگر ستون در جدول وجود نداشت اضافه می‌کند (Migration امن بدون از دست دادن داده)."""
        existing = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coldef}")

    # ------------------------------------------------
    # کاربران
    # ------------------------------------------------

    def get_user(self, user_id: int):
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return row

    def get_or_create_user(self, user_id: int, username: str, display_name: str):
        """اگر کاربر وجود نداشت، بسازد. همیشه Username/Display Name را هم به‌روز کند."""
        with self.transaction() as conn:
            row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO users (user_id, username, display_name, silver, gold, diamond, join_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        username or "",
                        display_name or "",
                        config.STARTING_SILVER,
                        config.STARTING_GOLD,
                        config.STARTING_DIAMOND,
                        time.time(),
                    ),
                )
                created = True
            else:
                conn.execute(
                    "UPDATE users SET username = ?, display_name = ? WHERE user_id = ?",
                    (username or "", display_name or "", user_id),
                )
                created = False
            row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
            return row, created

    def user_exists(self, user_id: int) -> bool:
        return self.get_user(user_id) is not None

    # ------------------------------------------------
    # موجودی (Balance)
    # ------------------------------------------------

    def get_balance(self, user_id: int, currency: str) -> int:
        row = self.get_user(user_id)
        if row is None:
            return 0
        return row[currency]

    def has_enough(self, user_id: int, currency: str, amount: int) -> bool:
        return self.get_balance(user_id, currency) >= amount

    def adjust_balance(self, conn, user_id: int, currency: str, delta: int):
        """
        فقط داخل یک تراکنش فعال (conn) صدا زده شود.
        اگر موجودی به منفی برسد، Exception می‌دهد (برای جلوگیری از باگ).
        """
        if currency not in ("silver", "gold", "diamond"):
            raise ValueError("Invalid currency")
        row = conn.execute(f"SELECT {currency} FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            raise ValueError("User not found")
        new_value = row[0] + delta
        if new_value < 0:
            raise ValueError("Insufficient balance")
        conn.execute(f"UPDATE users SET {currency} = ? WHERE user_id = ?", (new_value, user_id))
        return new_value

    def add_balance(self, user_id: int, currency: str, amount: int):
        """افزودن مستقیم و امن به موجودی (تراکنش خودش را می‌سازد). amount می‌تواند منفی باشد."""
        with self.transaction() as conn:
            return self.adjust_balance(conn, user_id, currency, amount)

    # ------------------------------------------------
    # آمار بازی
    # ------------------------------------------------

    def record_game_result(self, conn, user_id: int, won: bool, currency: str = "silver", amount: int = 0):
        """
        ثبت نتیجه یک بازی برای کاربر. باید داخل یک تراکنش فعال صدا زده شود.
        amount: مقدار برد یا باخت (مثبت)
        """
        games_played_inc = 1
        wins_inc = 1 if won else 0
        losses_inc = 0 if won else 1
        total_won_inc = 0
        total_lost_inc = 0
        gold_won_inc = 0
        diamond_won_inc = 0

        if won:
            if currency == "silver":
                total_won_inc = amount
            elif currency == "gold":
                gold_won_inc = amount
            elif currency == "diamond":
                diamond_won_inc = amount
        else:
            if currency == "silver":
                total_lost_inc = amount

        conn.execute(
            """
            UPDATE users SET
                games_played = games_played + ?,
                wins = wins + ?,
                losses = losses + ?,
                total_won = total_won + ?,
                total_lost = total_lost + ?,
                gold_won = gold_won + ?,
                diamond_won = diamond_won + ?
            WHERE user_id = ?
            """,
            (
                games_played_inc,
                wins_inc,
                losses_inc,
                total_won_inc,
                total_lost_inc,
                gold_won_inc,
                diamond_won_inc,
                user_id,
            ),
        )

    def increment_bets_count(self, conn, user_id: int):
        conn.execute("UPDATE users SET bets_count = bets_count + 1 WHERE user_id = ?", (user_id,))

    def record_draw(self, conn, user_id: int):
        """برای بازی‌هایی مثل دوز که می‌توانند با مساوی تمام شوند: فقط games_played را زیاد می‌کند."""
        conn.execute("UPDATE users SET games_played = games_played + 1 WHERE user_id = ?", (user_id,))

    # ------------------------------------------------
    # /gain
    # ------------------------------------------------

    def get_last_gain(self, user_id: int):
        row = self.get_user(user_id)
        return row["last_gain"] if row else None

    def set_last_gain(self, conn, user_id: int, ts: float):
        conn.execute("UPDATE users SET last_gain = ? WHERE user_id = ?", (ts, user_id))

    # ------------------------------------------------
    # Bets
    # ------------------------------------------------

    def create_bet(self, creator_id: int, stake: int, chat_id: int) -> int:
        with self.transaction() as conn:
            self.adjust_balance(conn, creator_id, "silver", -stake)
            cur = conn.execute(
                """
                INSERT INTO bets (creator_id, stake, status, chat_id, created_at)
                VALUES (?, ?, 'open', ?, ?)
                """,
                (creator_id, stake, chat_id, time.time()),
            )
            return cur.lastrowid

    def set_bet_message(self, bet_id: int, message_id: int):
        with self.transaction() as conn:
            conn.execute("UPDATE bets SET message_id = ? WHERE bet_id = ?", (message_id, bet_id))

    def get_bet(self, bet_id: int):
        conn = self._get_conn()
        return conn.execute("SELECT * FROM bets WHERE bet_id = ?", (bet_id,)).fetchone()

    def join_bet(self, bet_id: int, opponent_id: int):
        """
        تلاش امن برای پیوستن به یک Bet.
        خروجی: (success: bool, message: str, bet_row یا None)
        """
        with self.transaction() as conn:
            bet = conn.execute("SELECT * FROM bets WHERE bet_id = ?", (bet_id,)).fetchone()
            if bet is None:
                return False, "❌ Bet not found.", None
            if bet["status"] != "open":
                return False, "❌ This bet is no longer available.", None
            if bet["creator_id"] == opponent_id:
                return False, "❌ You cannot join your own bet.", None

            opp_row = conn.execute("SELECT silver FROM users WHERE user_id = ?", (opponent_id,)).fetchone()
            if opp_row is None or opp_row["silver"] < bet["stake"]:
                return False, "❌ You don't have enough Silver.", None

            # قفل بت: بلافاصله وضعیت را closed می‌کنیم تا دوبار Join ممکن نباشد
            conn.execute(
                "UPDATE bets SET status = 'closed', opponent_id = ? WHERE bet_id = ? AND status = 'open'",
                (opponent_id, bet_id),
            )
            if conn.total_changes == 0:
                return False, "❌ This bet is no longer available.", None

            # کسر موجودی حریف (موجودی سازنده در زمان ساخت بت قبلاً کسر شده)
            self.adjust_balance(conn, opponent_id, "silver", -bet["stake"])

            import random

            winner_id = random.choice([bet["creator_id"], opponent_id])
            loser_id = opponent_id if winner_id == bet["creator_id"] else bet["creator_id"]
            prize = bet["stake"] * 2

            self.adjust_balance(conn, winner_id, "silver", prize)

            conn.execute(
                "UPDATE bets SET status = 'finished', winner_id = ? WHERE bet_id = ?",
                (winner_id, bet_id),
            )

            self.record_game_result(conn, winner_id, True, "silver", bet["stake"])
            self.record_game_result(conn, loser_id, False, "silver", bet["stake"])
            self.increment_bets_count(conn, bet["creator_id"])
            self.increment_bets_count(conn, opponent_id)

            bet = conn.execute("SELECT * FROM bets WHERE bet_id = ?", (bet_id,)).fetchone()
            return True, "ok", bet

    def cancel_bet(self, bet_id: int, requester_id: int):
        """فقط سازنده Bet باز می‌تواند آن را لغو کند و Silver خودش را پس بگیرد."""
        with self.transaction() as conn:
            bet = conn.execute("SELECT * FROM bets WHERE bet_id = ?", (bet_id,)).fetchone()
            if bet is None or bet["status"] != "open":
                return False, "❌ This bet cannot be cancelled."
            if bet["creator_id"] != requester_id:
                return False, "❌ Only the creator can cancel this bet."
            conn.execute("UPDATE bets SET status = 'cancelled' WHERE bet_id = ?", (bet_id,))
            self.adjust_balance(conn, bet["creator_id"], "silver", bet["stake"])
            return True, "✅ Bet cancelled and Silver refunded."

    def expire_old_bets(self, minutes: int):
        """Betهای باز قدیمی‌تر از X دقیقه را منقضی و Silver را برمی‌گرداند."""
        cutoff = time.time() - minutes * 60
        with self.transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM bets WHERE status = 'open' AND created_at < ?", (cutoff,)
            ).fetchall()
            for bet in rows:
                conn.execute("UPDATE bets SET status = 'expired' WHERE bet_id = ?", (bet["bet_id"],))
                self.adjust_balance(conn, bet["creator_id"], "silver", bet["stake"])
            return rows

    # ------------------------------------------------
    # Lobbies (RPS / Last Survivor)
    # ------------------------------------------------

    def create_lobby(self, game_type: str, creator_id: int, stake: int, currency: str, max_players: int, chat_id: int):
        with self.transaction() as conn:
            self.adjust_balance(conn, creator_id, currency, -stake)
            cur = conn.execute(
                """
                INSERT INTO lobbies (game_type, creator_id, stake, currency, max_players, status, chat_id, created_at)
                VALUES (?, ?, ?, ?, ?, 'open', ?, ?)
                """,
                (game_type, creator_id, stake, currency, max_players, chat_id, time.time()),
            )
            lobby_id = cur.lastrowid
            conn.execute(
                "INSERT INTO lobby_players (lobby_id, user_id, joined_at) VALUES (?, ?, ?)",
                (lobby_id, creator_id, time.time()),
            )
            return lobby_id

    def set_lobby_message(self, lobby_id: int, message_id: int):
        with self.transaction() as conn:
            conn.execute("UPDATE lobbies SET message_id = ? WHERE lobby_id = ?", (message_id, lobby_id))

    def get_lobby(self, lobby_id: int):
        conn = self._get_conn()
        return conn.execute("SELECT * FROM lobbies WHERE lobby_id = ?", (lobby_id,)).fetchone()

    def get_lobby_players(self, lobby_id: int):
        conn = self._get_conn()
        return conn.execute(
            "SELECT * FROM lobby_players WHERE lobby_id = ? ORDER BY joined_at", (lobby_id,)
        ).fetchall()

    def join_lobby(self, lobby_id: int, user_id: int):
        with self.transaction() as conn:
            lobby = conn.execute("SELECT * FROM lobbies WHERE lobby_id = ?", (lobby_id,)).fetchone()
            if lobby is None or lobby["status"] != "open":
                return False, "❌ This game is no longer joinable.", None

            existing = conn.execute(
                "SELECT * FROM lobby_players WHERE lobby_id = ? AND user_id = ?", (lobby_id, user_id)
            ).fetchone()
            if existing:
                return False, "❌ You already joined this game.", None

            count = conn.execute(
                "SELECT COUNT(*) as c FROM lobby_players WHERE lobby_id = ?", (lobby_id,)
            ).fetchone()["c"]
            if count >= lobby["max_players"]:
                return False, "❌ This game lobby is full.", None

            user_row = conn.execute(
                f"SELECT {lobby['currency']} FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            if user_row is None or user_row[0] < lobby["stake"]:
                return False, f"❌ You don't have enough {lobby['currency'].capitalize()}.", None

            self.adjust_balance(conn, user_id, lobby["currency"], -lobby["stake"])
            conn.execute(
                "INSERT INTO lobby_players (lobby_id, user_id, joined_at) VALUES (?, ?, ?)",
                (lobby_id, user_id, time.time()),
            )
            lobby = conn.execute("SELECT * FROM lobbies WHERE lobby_id = ?", (lobby_id,)).fetchone()
            return True, "ok", lobby

    def start_lobby(self, lobby_id: int):
        with self.transaction() as conn:
            conn.execute("UPDATE lobbies SET status = 'started' WHERE lobby_id = ?", (lobby_id,))

    def try_start_lobby(self, lobby_id: int, requester_id: int):
        """فقط سازنده و فقط یک‌بار می‌تواند بازی را شروع کند (جلوگیری از Double Click)."""
        with self.transaction() as conn:
            lobby = conn.execute("SELECT * FROM lobbies WHERE lobby_id = ?", (lobby_id,)).fetchone()
            if lobby is None or lobby["status"] != "open":
                return False, "❌ This game cannot be started."
            if lobby["creator_id"] != requester_id:
                return False, "❌ Only the creator can start this game."
            count = conn.execute(
                "SELECT COUNT(*) as c FROM lobby_players WHERE lobby_id = ?", (lobby_id,)
            ).fetchone()["c"]
            if count < 2:
                return False, "❌ Need at least 2 players to start."
            conn.execute(
                "UPDATE lobbies SET status = 'started' WHERE lobby_id = ? AND status = 'open'",
                (lobby_id,),
            )
            if conn.total_changes == 0:
                return False, "❌ This game already started."
            return True, "ok"

    def cancel_lobby(self, lobby_id: int, requester_id: int):
        with self.transaction() as conn:
            lobby = conn.execute("SELECT * FROM lobbies WHERE lobby_id = ?", (lobby_id,)).fetchone()
            if lobby is None or lobby["status"] != "open":
                return False, "❌ This game cannot be cancelled."
            if lobby["creator_id"] != requester_id:
                return False, "❌ Only the creator can cancel this game."
            players = conn.execute(
                "SELECT * FROM lobby_players WHERE lobby_id = ?", (lobby_id,)
            ).fetchall()
            for p in players:
                self.adjust_balance(conn, p["user_id"], lobby["currency"], lobby["stake"])
            conn.execute("UPDATE lobbies SET status = 'cancelled' WHERE lobby_id = ?", (lobby_id,))
            return True, "✅ Game cancelled, stakes refunded."

    def finish_lobby_survivor(self, lobby_id: int, winner_id: int, prize_pool: int, currency: str):
        """پرداخت جایزه برنده Last Survivor و ثبت آمار همه شرکت‌کنندگان."""
        with self.transaction() as conn:
            players = conn.execute(
                "SELECT * FROM lobby_players WHERE lobby_id = ?", (lobby_id,)
            ).fetchall()
            self.adjust_balance(conn, winner_id, currency, prize_pool)
            lobby = conn.execute("SELECT * FROM lobbies WHERE lobby_id = ?", (lobby_id,)).fetchone()
            for p in players:
                won = p["user_id"] == winner_id
                amount = prize_pool if won else lobby["stake"]
                self.record_game_result(conn, p["user_id"], won, currency, amount)
            conn.execute(
                "UPDATE lobbies SET status = 'finished', winner_id = ? WHERE lobby_id = ?",
                (winner_id, lobby_id),
            )

    def try_set_choice(self, lobby_id: int, user_id: int, choice: str) -> bool:
        """فقط اگر بازیکن قبلاً انتخاب نکرده باشد، انتخاب را ثبت می‌کند. جلوگیری از Double Click."""
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT choice FROM lobby_players WHERE lobby_id = ? AND user_id = ?",
                (lobby_id, user_id),
            ).fetchone()
            if row is None or row["choice"] is not None:
                return False
            conn.execute(
                "UPDATE lobby_players SET choice = ? WHERE lobby_id = ? AND user_id = ?",
                (choice, lobby_id, user_id),
            )
            return True

    def finish_lobby_rps(self, lobby_id: int, winner_id, currency: str, prize_pool: int):
        """
        پایان بازی سنگ‌کاغذقیچی تک‌راندی (نسخه قدیمی).
        از نسخه فعلی ربات به بعد، RPS به صورت Best-of-N اجرا می‌شود و به‌جای این متد،
        از resolve_rps_round استفاده می‌کند. این متد فقط برای سازگاری نگه داشته شده و
        دیگر در جریان بازی صدا زده نمی‌شود.
        """
        with self.transaction() as conn:
            players = conn.execute(
                "SELECT * FROM lobby_players WHERE lobby_id = ?", (lobby_id,)
            ).fetchall()
            lobby = conn.execute("SELECT * FROM lobbies WHERE lobby_id = ?", (lobby_id,)).fetchone()
            if winner_id is None:
                # مساوی: مبلغ به هر دو برگردد
                for p in players:
                    self.adjust_balance(conn, p["user_id"], currency, lobby["stake"])
            else:
                self.adjust_balance(conn, winner_id, currency, prize_pool)
                for p in players:
                    won = p["user_id"] == winner_id
                    amount = prize_pool if won else lobby["stake"]
                    self.record_game_result(conn, p["user_id"], won, currency, amount)
            conn.execute(
                "UPDATE lobbies SET status = 'finished', winner_id = ? WHERE lobby_id = ?",
                (winner_id, lobby_id),
            )

    def resolve_rps_round(self, lobby_id: int):
        """
        وقتی هر دو بازیکن انتخاب راند فعلی را ثبت کرده باشند صدا زده می‌شود.
        بازی Best-of-N است (تعداد راند برد لازم از config.RPS_ROUNDS_TO_WIN خوانده می‌شود):
        - اگر راند مساوی شود، امتیازی داده نمی‌شود و همان راند دوباره بازی می‌شود.
        - اگر یکی از بازیکنان به تعداد راند لازم برسد، کل مسابقه تمام و جایزه پرداخت می‌شود.
        - در غیر این صورت راند بعدی شروع می‌شود.

        خروجی: یک dict با اطلاعات نتیجه راند، یا None اگر هنوز هر دو انتخاب نکرده‌اند.
        """
        with self.transaction() as conn:
            lobby = conn.execute("SELECT * FROM lobbies WHERE lobby_id = ?", (lobby_id,)).fetchone()
            players = conn.execute(
                "SELECT * FROM lobby_players WHERE lobby_id = ? ORDER BY joined_at", (lobby_id,)
            ).fetchall()
            if len(players) < 2:
                return None
            p1, p2 = players[0], players[1]
            if p1["choice"] is None or p2["choice"] is None:
                return None  # هنوز هر دو بازیکن انتخاب نکرده‌اند

            outcome = games.rps_winner(p1["choice"], p2["choice"])
            info = {
                "round": lobby["rps_round"],
                "p1_choice": p1["choice"],
                "p2_choice": p2["choice"],
                "tie": outcome == 0,
                "game_finished": False,
                "winner_user_id": None,
                "match_winner_id": None,
                "score_creator": lobby["rps_score_creator"],
                "score_opponent": lobby["rps_score_opponent"],
            }

            if outcome == 0:
                # مساوی: امتیاز عوض نمی‌شود، فقط انتخاب‌ها ریست می‌شوند تا همین راند دوباره بازی شود
                conn.execute("UPDATE lobby_players SET choice = NULL WHERE lobby_id = ?", (lobby_id,))
                return info

            if outcome == 1:
                score_creator = lobby["rps_score_creator"] + 1
                score_opponent = lobby["rps_score_opponent"]
                round_winner_id = p1["user_id"]
                conn.execute(
                    "UPDATE lobbies SET rps_score_creator = ? WHERE lobby_id = ?",
                    (score_creator, lobby_id),
                )
            else:
                score_creator = lobby["rps_score_creator"]
                score_opponent = lobby["rps_score_opponent"] + 1
                round_winner_id = p2["user_id"]
                conn.execute(
                    "UPDATE lobbies SET rps_score_opponent = ? WHERE lobby_id = ?",
                    (score_opponent, lobby_id),
                )

            info["winner_user_id"] = round_winner_id
            info["score_creator"] = score_creator
            info["score_opponent"] = score_opponent

            game_finished = max(score_creator, score_opponent) >= config.RPS_ROUNDS_TO_WIN
            info["game_finished"] = game_finished

            if game_finished:
                match_winner_id = p1["user_id"] if score_creator > score_opponent else p2["user_id"]
                loser_id = p2["user_id"] if match_winner_id == p1["user_id"] else p1["user_id"]
                prize = lobby["stake"] * 2
                self.adjust_balance(conn, match_winner_id, lobby["currency"], prize)
                self.record_game_result(
                    conn, match_winner_id, True, lobby["currency"], prize - lobby["stake"]
                )
                self.record_game_result(conn, loser_id, False, lobby["currency"], lobby["stake"])
                conn.execute(
                    "UPDATE lobbies SET status = 'finished', winner_id = ? WHERE lobby_id = ?",
                    (match_winner_id, lobby_id),
                )
                info["match_winner_id"] = match_winner_id
            else:
                conn.execute(
                    "UPDATE lobbies SET rps_round = rps_round + 1 WHERE lobby_id = ?", (lobby_id,)
                )
                conn.execute("UPDATE lobby_players SET choice = NULL WHERE lobby_id = ?", (lobby_id,))

            return info

    def expire_old_lobbies(self, minutes: int):
        cutoff = time.time() - minutes * 60
        with self.transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM lobbies WHERE status = 'open' AND created_at < ?", (cutoff,)
            ).fetchall()
            for lobby in rows:
                players = conn.execute(
                    "SELECT * FROM lobby_players WHERE lobby_id = ?", (lobby["lobby_id"],)
                ).fetchall()
                for p in players:
                    self.adjust_balance(conn, p["user_id"], lobby["currency"], lobby["stake"])
                conn.execute(
                    "UPDATE lobbies SET status = 'expired' WHERE lobby_id = ?", (lobby["lobby_id"],)
                )
            return rows

    # ------------------------------------------------
    # Tic-Tac-Toe (دوز)
    # این بازی بدون شرط/جایزه است؛ کل وضعیت بازی (board/turn/status) در دیتابیس
    # نگه‌داری می‌شود تا Restart شدن ربات باعث از بین رفتن بازی‌های در حال انجام نشود.
    # ------------------------------------------------

    def create_ttt_game(self, creator_id: int, chat_id: int) -> int:
        with self.transaction() as conn:
            cur = conn.execute(
                """
                INSERT INTO ttt_games (player_x, board, turn, status, chat_id, created_at)
                VALUES (?, '.........', 'X', 'open', ?, ?)
                """,
                (creator_id, chat_id, time.time()),
            )
            return cur.lastrowid

    def set_ttt_message(self, game_id: int, message_id: int):
        with self.transaction() as conn:
            conn.execute("UPDATE ttt_games SET message_id = ? WHERE game_id = ?", (message_id, game_id))

    def get_ttt_game(self, game_id: int):
        conn = self._get_conn()
        return conn.execute("SELECT * FROM ttt_games WHERE game_id = ?", (game_id,)).fetchone()

    def get_active_ttt_for_user(self, user_id: int):
        """آخرین بازی باز یا در حال انجام کاربر را برمی‌گرداند (برای جلوگیری از چند بازی هم‌زمان)."""
        conn = self._get_conn()
        return conn.execute(
            "SELECT * FROM ttt_games WHERE status IN ('open', 'active') AND (player_x = ? OR player_o = ?) "
            "ORDER BY created_at DESC LIMIT 1",
            (user_id, user_id),
        ).fetchone()

    def join_ttt_game(self, game_id: int, joiner_id: int):
        with self.transaction() as conn:
            game = conn.execute("SELECT * FROM ttt_games WHERE game_id = ?", (game_id,)).fetchone()
            if game is None or game["status"] != "open":
                return False, "❌ This game is no longer joinable.", None
            if game["player_x"] == joiner_id:
                return False, "❌ You cannot join your own game.", None
            conn.execute(
                "UPDATE ttt_games SET player_o = ?, status = 'active' WHERE game_id = ? AND status = 'open'",
                (joiner_id, game_id),
            )
            if conn.total_changes == 0:
                return False, "❌ This game is no longer joinable.", None
            game = conn.execute("SELECT * FROM ttt_games WHERE game_id = ?", (game_id,)).fetchone()
            return True, "ok", game

    def cancel_ttt_game(self, game_id: int, requester_id: int):
        with self.transaction() as conn:
            game = conn.execute("SELECT * FROM ttt_games WHERE game_id = ?", (game_id,)).fetchone()
            if game is None or game["status"] != "open":
                return False, "❌ This game cannot be cancelled."
            if game["player_x"] != requester_id:
                return False, "❌ Only the creator can cancel this game."
            conn.execute("UPDATE ttt_games SET status = 'cancelled' WHERE game_id = ?", (game_id,))
            return True, "✅ Game cancelled."

    def make_ttt_move(self, game_id: int, user_id: int, cell_index: int):
        """
        یک حرکت را با اعتبارسنجی کامل ثبت می‌کند (نوبت درست، خانه خالی، بازی فعال).
        خروجی: (success, message, game_row_or_None, finished, winner_id_or_None, is_draw)
        """
        with self.transaction() as conn:
            game = conn.execute("SELECT * FROM ttt_games WHERE game_id = ?", (game_id,)).fetchone()
            if game is None or game["status"] != "active":
                return False, "❌ This game is not active.", None, False, None, False

            expected_player = game["player_x"] if game["turn"] == "X" else game["player_o"]
            if user_id != expected_player:
                return False, "❌ It's not your turn.", None, False, None, False

            if cell_index < 0 or cell_index > 8:
                return False, "❌ Invalid move.", None, False, None, False

            board = list(game["board"])
            if board[cell_index] != ".":
                return False, "❌ That cell is already taken.", None, False, None, False

            board[cell_index] = game["turn"]
            new_board = "".join(board)

            winner_symbol = games.check_ttt_winner(new_board)
            is_draw = winner_symbol is None and "." not in new_board

            if winner_symbol:
                winner_id = game["player_x"] if winner_symbol == "X" else game["player_o"]
                loser_id = game["player_o"] if winner_symbol == "X" else game["player_x"]
                conn.execute(
                    "UPDATE ttt_games SET board = ?, status = 'finished', winner_id = ? WHERE game_id = ?",
                    (new_board, winner_id, game_id),
                )
                self.record_game_result(conn, winner_id, True, "silver", 0)
                self.record_game_result(conn, loser_id, False, "silver", 0)
                game = conn.execute("SELECT * FROM ttt_games WHERE game_id = ?", (game_id,)).fetchone()
                return True, "ok", game, True, winner_id, False

            if is_draw:
                conn.execute(
                    "UPDATE ttt_games SET board = ?, status = 'finished' WHERE game_id = ?",
                    (new_board, game_id),
                )
                self.record_draw(conn, game["player_x"])
                self.record_draw(conn, game["player_o"])
                game = conn.execute("SELECT * FROM ttt_games WHERE game_id = ?", (game_id,)).fetchone()
                return True, "ok", game, True, None, True

            next_turn = "O" if game["turn"] == "X" else "X"
            conn.execute(
                "UPDATE ttt_games SET board = ?, turn = ? WHERE game_id = ?",
                (new_board, next_turn, game_id),
            )
            game = conn.execute("SELECT * FROM ttt_games WHERE game_id = ?", (game_id,)).fetchone()
            return True, "ok", game, False, None, False

    # ------------------------------------------------
    # Exchange
    # ------------------------------------------------

    def exchange_silver(self, user_id: int, silver_amount: int, target_currency: str):
        rate = config.EXCHANGE_RATES.get(f"silver_to_{target_currency}")
        if rate is None:
            return False, "❌ Invalid currency.", 0
        if silver_amount % rate != 0:
            return False, f"❌ Amount must be a multiple of {rate}.", 0
        target_amount = silver_amount // rate
        if target_amount <= 0:
            return False, "❌ Amount too small.", 0
        with self.transaction() as conn:
            row = conn.execute("SELECT silver FROM users WHERE user_id = ?", (user_id,)).fetchone()
            if row is None or row["silver"] < silver_amount:
                return False, "❌ Not enough Silver.", 0
            self.adjust_balance(conn, user_id, "silver", -silver_amount)
            self.adjust_balance(conn, user_id, target_currency, target_amount)
        return True, "ok", target_amount

    # ------------------------------------------------
    # Leaderboard
    # ------------------------------------------------

    def leaderboard(self, order_by: str, limit: int):
        allowed = {
            "silver": "silver DESC",
            "wins": "wins DESC",
            "games": "games_played DESC",
            "winrate": None,  # special handling below
            "diamond": "diamond DESC",
            "gold": "gold DESC",
        }
        conn = self._get_conn()
        if order_by == "winrate":
            rows = conn.execute(
                """
                SELECT *, CAST(wins AS REAL) / (games_played) as winrate
                FROM users
                WHERE games_played >= 5
                ORDER BY winrate DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return rows
        clause = allowed.get(order_by, "silver DESC")
        rows = conn.execute(f"SELECT * FROM users ORDER BY {clause} LIMIT ?", (limit,)).fetchall()
        return rows

    # ------------------------------------------------
    # Admin
    # ------------------------------------------------

    def admin_stats(self):
        conn = self._get_conn()
        users_count = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
        games_count = conn.execute("SELECT SUM(games_played) as c FROM users").fetchone()["c"] or 0
        totals = conn.execute(
            "SELECT SUM(silver) as s, SUM(gold) as g, SUM(diamond) as d FROM users"
        ).fetchone()
        return {
            "users": users_count,
            "games": games_count,
            "total_silver": totals["s"] or 0,
            "total_gold": totals["g"] or 0,
            "total_diamond": totals["d"] or 0,
        }

    def admin_adjust_balance(self, admin_id: int, target_user_id: int, currency: str, amount: int, note: str = ""):
        with self.transaction() as conn:
            row = conn.execute("SELECT user_id FROM users WHERE user_id = ?", (target_user_id,)).fetchone()
            if row is None:
                return False, "❌ User not found in database."
            new_val = self.adjust_balance(conn, target_user_id, currency, amount)
            conn.execute(
                """
                INSERT INTO admin_logs (admin_id, action, target_user_id, amount, currency, note, timestamp)
                VALUES (?, 'adjust_balance', ?, ?, ?, ?, ?)
                """,
                (admin_id, target_user_id, amount, currency, note, time.time()),
            )
            return True, new_val

    def admin_reset_user(self, admin_id: int, target_user_id: int):
        with self.transaction() as conn:
            row = conn.execute("SELECT user_id FROM users WHERE user_id = ?", (target_user_id,)).fetchone()
            if row is None:
                return False, "❌ User not found."
            conn.execute(
                """
                UPDATE users SET silver = ?, gold = ?, diamond = ?, games_played = 0, wins = 0,
                losses = 0, bets_count = 0, total_won = 0, total_lost = 0, gold_won = 0, diamond_won = 0
                WHERE user_id = ?
                """,
                (config.STARTING_SILVER, config.STARTING_GOLD, config.STARTING_DIAMOND, target_user_id),
            )
            conn.execute(
                """
                INSERT INTO admin_logs (admin_id, action, target_user_id, amount, currency, note, timestamp)
                VALUES (?, 'reset_user', ?, NULL, NULL, 'full reset', ?)
                """,
                (admin_id, target_user_id, time.time()),
            )
            return True, "✅ User has been reset."

    def set_game_status(self, admin_id: int, game_key: str, enabled: bool):
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO game_status (game_key, enabled) VALUES (?, ?) "
                "ON CONFLICT(game_key) DO UPDATE SET enabled = excluded.enabled",
                (game_key, 1 if enabled else 0),
            )
            conn.execute(
                """
                INSERT INTO admin_logs (admin_id, action, target_user_id, amount, currency, note, timestamp)
                VALUES (?, 'toggle_game', NULL, NULL, NULL, ?, ?)
                """,
                (admin_id, f"{game_key} -> {'ON' if enabled else 'OFF'}", time.time()),
            )

    def is_game_enabled(self, game_key: str) -> bool:
        conn = self._get_conn()
        row = conn.execute("SELECT enabled FROM game_status WHERE game_key = ?", (game_key,)).fetchone()
        if row is None:
            return True
        return bool(row["enabled"])

    def all_game_statuses(self):
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM game_status").fetchall()
        return {r["game_key"]: bool(r["enabled"]) for r in rows}

    # ==================================================================
    # 🏙️ CITY / LAND / PROPERTY ECONOMY
    # ==================================================================

    # ------------------------------------------------
    # Pricing helpers (بدون تغییر در دیتابیس، فقط محاسبه)
    # ------------------------------------------------

    def compute_public_zone(self, x: int, y: int):
        """Zone و ضریب قیمت یک مختصات در Public City را برمی‌گرداند."""
        center = (config.CITY_GRID_SIZE - 1) / 2.0
        distance = max(abs(x - center), abs(y - center))  # Chebyshev distance
        for zone in config.PUBLIC_CITY_ZONES:
            if distance <= zone["max_distance"]:
                return zone
        return config.PUBLIC_CITY_ZONES[-1]

    def compute_public_plot_price(self, x: int, y: int) -> int:
        zone = self.compute_public_zone(x, y)
        return round(config.PUBLIC_CITY_BASE_PRICE * zone["multiplier"])

    def compute_personal_plot_price(self, city_type: str) -> int:
        return config.CITY_PLOT_BASE_PRICE[city_type]

    def get_building_def(self, city_type: str, building_key: str):
        return config.CITY_BUILDINGS.get(city_type, {}).get(building_key)

    def compute_building_stats(self, city_type: str, building_key: str, level: int, is_public: bool):
        """
        مقادیر یک Building در یک Level مشخص را برمی‌گرداند:
        (value, income, base_tax_rate, tax_volatility)
        Public City از همان تعریف Building استفاده می‌کند، فقط با ضرایب بالاتر.
        """
        b = self.get_building_def(city_type, building_key)
        if b is None:
            return None
        value_mult = config.PUBLIC_CITY_VALUE_MULTIPLIER if is_public else 1.0
        income_mult = config.PUBLIC_CITY_INCOME_MULTIPLIER if is_public else 1.0
        value = b["base_value"] * (b["value_growth"] ** (level - 1)) * value_mult
        income = b["base_income"] * (b["income_growth"] ** (level - 1)) * income_mult
        return round(value), round(income), b["base_tax_rate"], b["tax_volatility"]

    def compute_build_cost(self, city_type: str, building_key: str, is_public: bool) -> int:
        b = self.get_building_def(city_type, building_key)
        mult = config.PUBLIC_CITY_BUILD_COST_MULTIPLIER if is_public else 1.0
        return round(b["build_cost"] * mult)

    def compute_upgrade_cost(self, city_type: str, building_key: str, current_level: int, is_public: bool) -> int:
        b = self.get_building_def(city_type, building_key)
        mult = config.PUBLIC_CITY_BUILD_COST_MULTIPLIER if is_public else 1.0
        cost = b["upgrade_cost_base"] * (b["upgrade_cost_growth"] ** (current_level - 1))
        return round(cost * mult)

    # ------------------------------------------------
    # Plot lookup
    # ------------------------------------------------

    def get_plot(self, city_type: str, x: int, y: int, personal_owner_id: int = None):
        conn = self._get_conn()
        if city_type == "public":
            return conn.execute(
                "SELECT * FROM plots WHERE city_type = 'public' AND x = ? AND y = ?", (x, y)
            ).fetchone()
        return conn.execute(
            "SELECT * FROM plots WHERE city_type = ? AND owner_id = ? AND x = ? AND y = ?",
            (city_type, personal_owner_id, x, y),
        ).fetchone()

    def get_plots_map(self, city_type: str, owner_id: int = None):
        """برای رسم گرید: دیکشنری {(x, y): plot_row} برای تمام Plotهای مالکیت‌دار آن نوع شهر."""
        conn = self._get_conn()
        if city_type == "public":
            rows = conn.execute("SELECT * FROM plots WHERE city_type = 'public'").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM plots WHERE city_type = ? AND owner_id = ?", (city_type, owner_id)
            ).fetchall()
        return {(r["x"], r["y"]): r for r in rows}

    def get_owned_plots_for_user(self, user_id: int, city_type: str = None):
        conn = self._get_conn()
        if city_type:
            return conn.execute(
                "SELECT * FROM plots WHERE owner_id = ? AND city_type = ?", (user_id, city_type)
            ).fetchall()
        return conn.execute("SELECT * FROM plots WHERE owner_id = ?", (user_id,)).fetchall()

    # ------------------------------------------------
    # Buy / Build / Upgrade / Sell (Atomic)
    # ------------------------------------------------

    def buy_personal_plot(self, user_id: int, city_type: str, x: int, y: int):
        price = self.compute_personal_plot_price(city_type)
        now = time.time()
        try:
            with self.transaction() as conn:
                try:
                    conn.execute(
                        """
                        INSERT INTO plots
                            (city_type, owner_id, x, y, purchase_price, current_value,
                             building_key, building_level, tax_debt, debt_since, last_settlement, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, NULL, 0, 0, NULL, ?, ?)
                        """,
                        (city_type, user_id, x, y, price, price, now, now),
                    )
                except sqlite3.IntegrityError:
                    raise ValueError("taken")
                row = conn.execute("SELECT silver FROM users WHERE user_id = ?", (user_id,)).fetchone()
                if row is None or row["silver"] < price:
                    raise ValueError("insufficient")
                self.adjust_balance(conn, user_id, "silver", -price)
        except ValueError as e:
            if str(e) == "taken":
                return False, "❌ You already own this plot.", None
            return False, "❌ You don't have enough Silver.", None
        return True, "ok", self.get_plot(city_type, x, y, user_id)

    def buy_public_plot(self, user_id: int, x: int, y: int):
        price = self.compute_public_plot_price(x, y)
        now = time.time()
        try:
            with self.transaction() as conn:
                try:
                    conn.execute(
                        """
                        INSERT INTO plots
                            (city_type, owner_id, x, y, purchase_price, current_value,
                             building_key, building_level, tax_debt, debt_since, last_settlement, created_at)
                        VALUES ('public', ?, ?, ?, ?, ?, NULL, 0, 0, NULL, ?, ?)
                        """,
                        (user_id, x, y, price, price, now, now),
                    )
                except sqlite3.IntegrityError:
                    raise ValueError("taken")
                row = conn.execute("SELECT diamond FROM users WHERE user_id = ?", (user_id,)).fetchone()
                if row is None or row["diamond"] < price:
                    raise ValueError("insufficient")
                self.adjust_balance(conn, user_id, "diamond", -price)
        except ValueError as e:
            if str(e) == "taken":
                return False, "❌ This plot was just taken by someone else.", None
            return False, "❌ You don't have enough Diamond.", None
        return True, "ok", self.get_plot("public", x, y)

    def build_building(self, user_id: int, city_type: str, x: int, y: int, building_key: str):
        if city_type not in ("commercial", "industrial"):
            return False, "❌ You can't build on this type of land.", None
        b = self.get_building_def(city_type, building_key)
        if b is None:
            return False, "❌ Unknown building type.", None

        is_public = False
        cost = self.compute_build_cost(city_type, building_key, is_public)
        currency = config.CITY_PERSONAL_CURRENCY

        try:
            with self.transaction() as conn:
                plot = conn.execute(
                    "SELECT * FROM plots WHERE city_type = ? AND owner_id = ? AND x = ? AND y = ?",
                    (city_type, user_id, x, y),
                ).fetchone()
                if plot is None:
                    raise ValueError("not_owned")
                if plot["building_key"] is not None:
                    raise ValueError("already_built")
                row = conn.execute(f"SELECT {currency} FROM users WHERE user_id = ?", (user_id,)).fetchone()
                if row is None or row[currency] < cost:
                    raise ValueError("insufficient")
                self.adjust_balance(conn, user_id, currency, -cost)
                value, _income, _rate, _vol = self.compute_building_stats(city_type, building_key, 1, is_public)
                new_value = plot["purchase_price"] + value
                conn.execute(
                    """
                    UPDATE plots SET building_key = ?, building_level = 1, current_value = ?
                    WHERE plot_id = ?
                    """,
                    (building_key, new_value, plot["plot_id"]),
                )
        except ValueError as e:
            reason = str(e)
            if reason == "not_owned":
                return False, "❌ You don't own this plot.", None
            if reason == "already_built":
                return False, "❌ This plot already has a building.", None
            return False, f"❌ You don't have enough {currency.capitalize()}.", None
        return True, "ok", self.get_plot(city_type, x, y, user_id)

    def upgrade_building(self, user_id: int, city_type: str, x: int, y: int):
        currency = config.CITY_PERSONAL_CURRENCY
        try:
            with self.transaction() as conn:
                plot = conn.execute(
                    "SELECT * FROM plots WHERE city_type = ? AND owner_id = ? AND x = ? AND y = ?",
                    (city_type, user_id, x, y),
                ).fetchone()
                if plot is None:
                    raise ValueError("not_owned")
                if plot["building_key"] is None:
                    raise ValueError("no_building")
                if plot["building_level"] >= config.CITY_MAX_BUILDING_LEVEL:
                    raise ValueError("max_level")
                cost = self.compute_upgrade_cost(city_type, plot["building_key"], plot["building_level"], False)
                row = conn.execute(f"SELECT {currency} FROM users WHERE user_id = ?", (user_id,)).fetchone()
                if row is None or row[currency] < cost:
                    raise ValueError("insufficient")
                self.adjust_balance(conn, user_id, currency, -cost)
                new_level = plot["building_level"] + 1
                value, _income, _rate, _vol = self.compute_building_stats(
                    city_type, plot["building_key"], new_level, False
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
        return True, "ok", self.get_plot(city_type, x, y, user_id)

    def sell_plot(self, user_id: int, city_type: str, x: int, y: int):
        currency = "diamond" if city_type == "public" else "silver"
        try:
            with self.transaction() as conn:
                if city_type == "public":
                    plot = conn.execute(
                        "SELECT * FROM plots WHERE city_type = 'public' AND owner_id = ? AND x = ? AND y = ?",
                        (user_id, x, y),
                    ).fetchone()
                else:
                    plot = conn.execute(
                        "SELECT * FROM plots WHERE city_type = ? AND owner_id = ? AND x = ? AND y = ?",
                        (city_type, user_id, x, y),
                    ).fetchone()
                if plot is None:
                    raise ValueError("not_owned")
                refund = round(plot["current_value"] * config.CITY_SELL_PERCENTAGE)
                conn.execute("DELETE FROM plots WHERE plot_id = ?", (plot["plot_id"],))
                self.adjust_balance(conn, user_id, currency, refund)
        except ValueError:
            return False, "❌ You don't own this plot.", 0
        return True, "ok", refund

    # ------------------------------------------------
    # Settlement (Income/Tax خودکار، امن در برابر Offline بودن بات)
    # ------------------------------------------------

    def _settle_plot_row(self, conn, plot, now: float):
        """
        یک Plot را برای تمام دوره‌های کامل سپری‌شده تسویه می‌کند.
        باید داخل یک تراکنش فعال (conn) صدا زده شود. خروجی dict خلاصه تسویه یا None
        اگر هنوز حتی یک دوره کامل نگذشته باشد.
        """
        interval = config.CITY_SETTLEMENT_INTERVAL_SECONDS
        elapsed = now - plot["last_settlement"]
        periods = int(elapsed // interval)
        if periods <= 0:
            return None
        periods = min(periods, config.CITY_MAX_CATCHUP_PERIODS)

        city_type = plot["city_type"]
        is_public = city_type == "public"
        land_tax_rate = config.CITY_LAND_TAX_RATE.get(city_type, 0.0) if not is_public else 0.0
        land_value = plot["purchase_price"]

        had_debt_at_start = plot["tax_debt"] > 0
        skip_income = had_debt_at_start and config.CITY_DEBT_STOPS_INCOME

        building_def = self.get_building_def(city_type, plot["building_key"]) if plot["building_key"] else None

        total_income = 0
        total_tax = 0
        for _ in range(periods):
            period_tax = land_value * land_tax_rate
            period_income = 0
            if building_def and plot["building_level"] > 0:
                value, income, base_rate, vol = self.compute_building_stats(
                    city_type, plot["building_key"], plot["building_level"], is_public
                )
                low = max(config.CITY_TAX_RATE_ABS_MIN, base_rate * (1 - vol))
                high = min(config.CITY_TAX_RATE_ABS_MAX, base_rate * (1 + vol))
                if high < low:
                    high = low
                effective_rate = random.uniform(low, high)
                period_tax += value * effective_rate
                if not skip_income:
                    period_income = income
            total_income += round(period_income)
            total_tax += round(period_tax)

        currency = "diamond" if is_public else "silver"
        old_debt = plot["tax_debt"]
        total_due = total_tax + old_debt

        if total_income >= total_due:
            net_credit = total_income - total_due
            new_debt = 0
            if net_credit > 0:
                self.adjust_balance(conn, plot["owner_id"], currency, net_credit)
        else:
            shortfall = total_due - total_income
            bal_row = conn.execute(
                f"SELECT {currency} FROM users WHERE user_id = ?", (plot["owner_id"],)
            ).fetchone()
            balance = bal_row[currency] if bal_row else 0
            payable = min(balance, shortfall)
            if payable > 0:
                self.adjust_balance(conn, plot["owner_id"], currency, -payable)
            new_debt = shortfall - payable

        debt_since = plot["debt_since"]
        if new_debt > 0 and old_debt == 0:
            debt_since = now
        elif new_debt == 0:
            debt_since = None

        conn.execute(
            "UPDATE plots SET tax_debt = ?, debt_since = ?, last_settlement = ? WHERE plot_id = ?",
            (new_debt, debt_since, now, plot["plot_id"]),
        )

        return {
            "periods": periods,
            "income": total_income,
            "tax": total_tax,
            "old_debt": old_debt,
            "new_debt": new_debt,
        }

    def settle_user_city(self, user_id: int):
        """تمام Plotهای یک کاربر (شخصی + Public) را تسویه می‌کند. برای نمایش لحظه‌ای صدا زده می‌شود."""
        now = time.time()
        results = []
        with self.transaction() as conn:
            rows = conn.execute("SELECT * FROM plots WHERE owner_id = ?", (user_id,)).fetchall()
            for plot in rows:
                res = self._settle_plot_row(conn, plot, now)
                if res:
                    results.append(res)
        return results

    def settle_all_plots(self):
        """Job پس‌زمینه‌ای: همه Plotهای صاحب‌دار را برای Settlement بررسی می‌کند."""
        now = time.time()
        count = 0
        with self.transaction() as conn:
            rows = conn.execute("SELECT * FROM plots").fetchall()
            for plot in rows:
                res = self._settle_plot_row(conn, plot, now)
                if res:
                    count += 1
        return count

    # ------------------------------------------------
    # City Statistics & Leaderboards
    # ------------------------------------------------

    def city_stats_for_user(self, user_id: int):
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM plots WHERE owner_id = ?", (user_id,)).fetchall()
        stats = {t: 0 for t in config.CITY_PERSONAL_TYPES}
        stats["public"] = 0
        buildings = 0
        gross_income = 0
        total_tax = 0
        total_value = 0
        highest_level = 0
        for p in rows:
            stats[p["city_type"]] = stats.get(p["city_type"], 0) + 1
            total_value += p["current_value"]
            if p["building_key"]:
                buildings += 1
                is_public = p["city_type"] == "public"
                value, income, base_rate, _vol = self.compute_building_stats(
                    p["city_type"], p["building_key"], p["building_level"], is_public
                )
                gross_income += income
                total_tax += round(value * base_rate)
                highest_level = max(highest_level, p["building_level"])
            land_rate = config.CITY_LAND_TAX_RATE.get(p["city_type"], 0.0) if p["city_type"] != "public" else 0.0
            total_tax += round(p["purchase_price"] * land_rate)
        return {
            "residential": stats.get("residential", 0),
            "commercial": stats.get("commercial", 0),
            "industrial": stats.get("industrial", 0),
            "luxury": stats.get("luxury", 0),
            "public": stats.get("public", 0),
            "buildings": buildings,
            "gross_income": gross_income,
            "taxes": total_tax,
            "net_income": gross_income - total_tax,
            "total_value": total_value,
            "highest_level": highest_level,
        }

    def city_leaderboard(self, category: str, limit: int):
        conn = self._get_conn()
        if category == "richest":
            rows = conn.execute(
                "SELECT owner_id, SUM(current_value) as total FROM plots GROUP BY owner_id "
                "ORDER BY total DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [(r["owner_id"], r["total"]) for r in rows]

        if category == "most_plots":
            rows = conn.execute(
                "SELECT owner_id, COUNT(*) as total FROM plots GROUP BY owner_id ORDER BY total DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [(r["owner_id"], r["total"]) for r in rows]

        if category == "highest_level":
            rows = conn.execute(
                "SELECT owner_id, MAX(building_level) as total FROM plots WHERE building_level > 0 "
                "GROUP BY owner_id ORDER BY total DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [(r["owner_id"], r["total"]) for r in rows]

        if category == "public_plots":
            rows = conn.execute(
                "SELECT owner_id, COUNT(*) as total FROM plots WHERE city_type = 'public' "
                "GROUP BY owner_id ORDER BY total DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [(r["owner_id"], r["total"]) for r in rows]

        if category == "highest_value":
            rows = conn.execute(
                "SELECT owner_id, MAX(current_value) as total FROM plots GROUP BY owner_id "
                "ORDER BY total DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [(r["owner_id"], r["total"]) for r in rows]

        if category == "highest_income":
            rows = conn.execute("SELECT * FROM plots WHERE building_key IS NOT NULL").fetchall()
            totals = {}
            for p in rows:
                is_public = p["city_type"] == "public"
                _value, income, _rate, _vol = self.compute_building_stats(
                    p["city_type"], p["building_key"], p["building_level"], is_public
                )
                totals[p["owner_id"]] = totals.get(p["owner_id"], 0) + income
            ordered = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
            return ordered[:limit]

        return []


# نمونه (singleton) مشترک دیتابیس. تمام ماژول‌های دیگر (handlers.py, city.py و ...)
# باید همین یک نمونه را وارد کنند (from database import db) تا قفل تراکنش‌ها
# (self._lock) برای کل برنامه یکسان و سراسری باشد، نه جداگانه به ازای هر ماژول.
db = Database()
