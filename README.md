# 🎮 Virtual Economy & Games Telegram Bot

A fun, group-friendly Telegram bot with a **100% virtual** token economy (Silver, Gold,
Diamond) and a set of simple games and bets. **No real money, no crypto, no payments —
everything is just numbers in a SQLite database, for fun.**

Built with `python-telegram-bot` (async, v21) and SQLite. No Docker, no Redis, no
Postgres, no microservices — just one process you can run on a VPS or your own machine.

---

## 1. Features

- 💰 Three virtual currencies: **Silver** (common), **Gold** (mid-tier), **Diamond** (high-risk)
- 🎁 `/gain` — daily free Silver (once per 24h, random 1–100)
- 🎲 `/bet <amount>` — 1v1 Silver bet against anyone else in the group
- 🎲 `/dice <amount>` — guess even/odd or the exact roll (1–6)
- 🔢 `/numguess <amount>` — guess a number in a range you pick (harder range = bigger prize)
- 🔤 `/wordguess` — multiple-choice word game (Easy / Medium / Hard)
- ✊ `/rps <amount>` — Rock Paper Scissors for Gold, 1v1, **Best of 3** (first to 2 round wins takes the match; tied rounds replay automatically)
- 💎 `/survivor <amount>` — "Last Survivor": 2–6 players, Diamond, elimination-round game
- 🥇 `/survivorgold <amount>` — smaller Last Survivor for Gold, up to 3 players
- 🎰 `/slots <amount>` — Slot Machine: 3x3 grid, middle row is the payline, payouts fully configurable in `config.py`
- ❌⭕ `/tictactoe` (or `/ttt`) — graphical 1v1 Tic-Tac-Toe with inline-keyboard buttons, no stake, just for fun and stats
- 🏙️ `/city` — full City/Land/Property economy: own 4 personal 10x10 maps (Residential, Commercial, Industrial, Luxury) plus compete for plots in one shared Public City. Buy land, build businesses, upgrade them up to level 10, earn daily Silver income, pay dynamic daily tax (cheaper buildings have more volatile tax, expensive ones are more stable), and track it all in City Statistics and City Leaderboards. Public City plots cost Diamond and are priced by zone (Center is most expensive). See `config.py` for every price/rate/growth curve.
- 🏦 Exchange Silver → Gold / Diamond at rates you control from `config.py`
- 🏆 Leaderboards: richest, most wins, most games, best win rate, most Gold/Diamond
- 📊 Personal statistics and profile
- 🛠 Admin panel: view stats, add/remove tokens, reset a user, enable/disable any game (including the two new ones) —
  every balance change made by the admin is logged in the database

All values are stored keyed by **Telegram User ID** (not username), so nothing breaks if
someone changes their username.

---

## 2. Project structure

```
config.py      # every tunable setting (token, admin id, rates, cooldowns, limits, City economy...)
database.py    # all SQLite access — schema + safe balance transactions + City economy queries
games.py       # pure game logic (dice, number pick, RPS winner, elimination order, slots, tic-tac-toe...)
handlers.py    # all Telegram command/callback handlers for games, economy, admin
city.py        # City/Land/Property economy: maps, plots, buildings, tax settlement, its own handlers
utils.py       # message formatting & keyboard builders
bot.py         # entry point — wires everything together and starts polling
requirements.txt
.env.example
```

---

## 3. Requirements

- Python 3.10+
- A Telegram bot token from **@BotFather**

---

## 4. How to create the bot with BotFather

1. Open Telegram and search for **@BotFather**.
2. Send `/newbot`.
3. Choose a display name (e.g. `Friends Casino Bot`).
4. Choose a unique username ending in `bot` (e.g. `friends_casino_bot`).
5. BotFather will reply with a token that looks like:
   `123456789:AAExampleTokenReplaceThis`
   **Copy this token** — you'll need it in the next step.
6. (Optional but recommended) Send `/setprivacy` to BotFather, choose your bot, and
   select **Disable** — this lets the bot read `/commands` typed in group chats even
   when it's not explicitly mentioned. If you keep privacy **Enabled**, users can still
   use all commands by typing them directly (e.g. `/bet 50`), but the bot won't see
   other unrelated group messages, which is usually what you want anyway.
7. Add the bot to your friend group and make sure it has permission to send messages.

To get your own numeric Telegram user ID (needed for `ADMIN_ID`), message
**@userinfobot** on Telegram and it will reply with your ID.

---

## 5. Installation

```bash
# 1. Clone / copy the project files into a folder, then enter it
cd telegram-economy-bot

# 2. (Recommended) create a virtual environment
python3 -m venv venv
source venv/bin/activate      # on Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create your .env file from the example
cp .env.example .env
```

Now open `.env` and fill in:

```
BOT_TOKEN=123456789:AAExampleTokenReplaceThis   # <-- from BotFather, step 6.5 above
ADMIN_ID=123456789                               # <-- your numeric Telegram ID
DATABASE_PATH=bot_database.db                    # fine to leave as-is
```

**This is the only manual setup required.** Everything else (exchange rates, bet
limits, cooldowns, starting balances, which games are enabled) already has sensible
defaults inside `config.py`, and you can tweak any of them there — every important
value is a named constant near the top of the file, with a comment explaining it.

---

## 6. Running the bot

```bash
python bot.py
```

You should see:

```
YYYY-MM-DD HH:MM:SS - __main__ - INFO - Bot is starting...
```

The bot uses long polling, so no public URL or webhook setup is needed — just leave
the process running (e.g. inside `tmux`, `screen`, or as a `systemd` service on your
VPS).

To stop it, press `Ctrl+C`.

---

## 7. Quick usage guide (for your friends)

- `/start` — opens the main menu (Games, Balance, Exchange, Leaderboard, Statistics, Help)
- `/gain` — claim your free daily Silver
- `/bet 100` — create a Silver bet; anyone else can tap "Join Bet"
- `/dice 50` — pick Even/Odd or an exact number
- `/numguess 30` — pick a difficulty range, then a number
- `/wordguess` — pick a difficulty, then guess the word from 4 options
- `/rps 20` — challenge someone to Rock Paper Scissors for Gold
- `/survivor 15` — start a Diamond "Last Survivor" lobby (2–6 players)
- `/survivorgold 10` — smaller Gold version (2–3 players)
- `/exchange_gold 300` — convert 300 Silver into Gold (rate shown in the Exchange menu)
- `/exchange_diamond 2000` — convert Silver into Diamond
- `/balance`, `/stats`, `/profile` — quick shortcuts to your own info

## 8. Admin usage

Only the Telegram user ID set as `ADMIN_ID` can use these:

- `/admin` — opens the admin panel (stats + game on/off toggles)
- `/admin_add <user_id> <silver|gold|diamond> <amount>`
- `/admin_remove <user_id> <silver|gold|diamond> <amount>`
- `/admin_reset <user_id>` — resets a user's balances and stats to defaults

Every admin balance change is written to the `admin_logs` table in the database
(admin id, target user, amount, currency, and timestamp), so you always have a trail
of what was changed and by whom.

---

## 9. Configuration you may want to tweak (`config.py`)

| Setting | What it controls |
|---|---|
| `STARTING_SILVER/GOLD/DIAMOND` | Balances a brand-new user starts with |
| `GAIN_COOLDOWN_HOURS`, `GAIN_MIN/MAX_AMOUNT` | `/gain` daily reward |
| `EXCHANGE_RATES` | How much Silver is needed for 1 Gold / 1 Diamond |
| `BET_MIN/MAX_AMOUNT`, `BET_EXPIRE_MINUTES` | Bet limits and auto-expiry |
| `DICE_*`, `NUMBER_GUESS_RANGES`, `WORD_GUESS_*` | Payout multipliers per game |
| `RPS_*`, `SURVIVOR_DIAMOND_*`, `SURVIVOR_GOLD_*` | Multiplayer game limits |
| `DEFAULT_GAME_STATUS` | Which games are enabled by default (also togglable live via `/admin`) |

---

## 10. Notes on safety & anti-abuse (already implemented)

- All balance changes happen inside SQLite transactions (`BEGIN IMMEDIATE` + a Python
  lock), so two people clicking "Join" on the same bet at the same instant can't both
  win, and a user can never go negative.
- Bets and game lobbies use atomic "claim" updates (`UPDATE ... WHERE status = 'open'`)
  so only one Join can ever succeed.
- An in-memory "resolved" set additionally blocks double-processing of a single-player
  game result if someone double-taps a button quickly.
- A background job (every 5 minutes) automatically expires old, unmatched bets and
  game lobbies and refunds the stake.
- The creator of a bet/lobby cannot join their own game.
- All game/bet amounts are validated to be positive integers within configured limits.

---

## 11. Troubleshooting

**`RuntimeError: There is no current event loop in thread 'MainThread'`**
This happens on Python 3.14+, which removed automatic event-loop creation that
`python-telegram-bot` 21.x relies on internally. `bot.py` already works around this by
creating the loop manually before `run_polling()`. If you still see it, make sure
you're running the latest `bot.py` from this project, or use Python 3.11–3.13 instead.

**`httpx.ConnectError: All connection attempts failed` when sending messages, but
`getUpdates` requests succeed in the logs**
This means your machine can poll Telegram for updates but can't reliably reach it to
*send* messages — almost always a network/firewall issue on your side (a filtered or
unstable connection to Telegram, antivirus/firewall interference, or an unstable VPN),
not a bug in the bot. The bot's global error handler now catches this and logs a clean
warning instead of crashing, and it will keep retrying automatically. If it keeps
happening:
- If you're in a region where Telegram is filtered, set `PROXY_URL` in `.env` to a
  working proxy (see `.env.example` — HTTP or SOCKS5 proxies are supported; SOCKS5
  needs `pip install "httpx[socks]"`), then restart the bot.
- If you already use a VPN, try a different server/protocol — some VPN configurations
  handle short polling requests fine but drop larger POST requests.
- Test basic connectivity from the same machine, e.g. `curl https://api.telegram.org`.

## 12. If something needs manual attention

- **`.env`**: you must fill in `BOT_TOKEN` and `ADMIN_ID` — the bot will refuse to start
  otherwise (`bot.py` raises a clear error if `BOT_TOKEN` is empty).
- **`config.py`**: exchange rates, bet limits, and reward amounts are pre-filled with
  reasonable defaults but are yours to change — every constant has a comment.
- The SQLite file (`bot_database.db` by default) is created automatically on first run
  in the project folder — no manual database setup needed.
