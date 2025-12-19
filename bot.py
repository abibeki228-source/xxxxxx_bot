import os
import asyncio
import logging
import aiosqlite
from datetime import datetime, timedelta
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart

# ================= ЗАГРУЗКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ =================
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# ================= НАСТРОЙКИ =================
DB_NAME = "database.db"

ADMINS = [7726017677]  # список админов

REF_BONUS = 15
MAX_REFERRALS = 19
MIN_WITHDRAW = 300

CHEST_REWARD = 5
CHEST_COOLDOWN_HOURS = 24

WITHDRAW_MODE = "FAKE"  # FAKE / REAL
# ============================================

# ================= КЛАВИАТУРЫ =================
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💎 Заработать"), KeyboardButton(text="🔐 Сундук")],
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="ℹ️ Информация")],
        [KeyboardButton(text="✅ Активировать промокод"), KeyboardButton(text="💸 Вывод средств")]
    ],
    resize_keyboard=True
)

admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🔁 Режим вывода")],
        [KeyboardButton(text="➕ Создать промокод"), KeyboardButton(text="📢 Рассылка")],
        [KeyboardButton(text="⬅️ Назад")]
    ],
    resize_keyboard=True
)
# ==============================================

# ================= БАЗА ДАННЫХ =================
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0,
            withdrawn REAL DEFAULT 0,
            referrer_id INTEGER,
            referrals INTEGER DEFAULT 0
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS chest (
            user_id INTEGER PRIMARY KEY,
            last_open TEXT
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS promocodes (
            code TEXT PRIMARY KEY,
            reward REAL,
            active INTEGER
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS promo_used (
            user_id INTEGER,
            code TEXT
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS withdraw_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        await db.commit()

async def add_user(user_id, username, referrer_id=None):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO users (user_id, username, referrer_id) VALUES (?, ?, ?)",
            (user_id, username, referrer_id)
        )

        if referrer_id:
            cur = await db.execute("SELECT referrals FROM users WHERE user_id=?", (referrer_id,))
            ref = await cur.fetchone()
            if ref and ref[0] < MAX_REFERRALS:
                await db.execute(
                    "UPDATE users SET balance = balance + ?, referrals = referrals + 1 WHERE user_id=?",
                    (REF_BONUS, referrer_id)
                )

        await db.commit()

async def get_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        return await cur.fetchone()

async def get_stats():
    async with aiosqlite.connect(DB_NAME) as db:
        users = await db.execute_fetchone("SELECT COUNT(*) FROM users")
        balance = await db.execute_fetchone("SELECT SUM(balance) FROM users")
        withdrawn = await db.execute_fetchone("SELECT SUM(withdrawn) FROM users")
        return users[0], balance[0] or 0, withdrawn[0] or 0
# ==============================================

bot = Bot(TOKEN)
dp = Dispatcher()

# ================= START =================
@dp.message(CommandStart())
async def start(message: Message):
    args = message.text.split()
    referrer = int(args[1]) if len(args) > 1 and args[1].isdigit() else None

    if not await user_exists(message.from_user.id):
        await add_user(message.from_user.id, message.from_user.username, referrer)

    asyncio.create_task(bot.send_sticker(
        chat_id=message.chat.id,
        sticker="CAACAgIAAxkBAAE_egZpRcu9w8P831WwAAGyNka8PNo24aMAAgQBAAL3AsgPIA93O-mryEk2BA"
    ))

    await message.answer("🐻 Добро пожаловать!", reply_markup=keyboard)
# ================= ПРОФИЛЬ =================
@dp.message(F.text == "👤 Профиль")
async def profile(message: Message):
    user = await get_user(message.from_user.id)
    
    if not user:
        # Если пользователя нет в базе, создаём его
        await add_user(message.from_user.id, message.from_user.username)
        user = await get_user(message.from_user.id)

    # Отправляем данные профиля
    await message.answer(
        f"👤 Профиль\n"
        f"━━━━━━━━━━\n"
        f"🆔 ID: {user[0]}\n"
        f"💰 Баланс: {user[2]:.2f} RUB\n"
        f"👥 Приглашено: {user[5]}"
    )

# ================= ПРОВЕРКА СУЩЕСТВОВАНИЯ ПОЛЬЗОВАТЕЛЯ =================
async def user_exists(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,))
        return await cur.fetchone() is not None

# ================= ЗАРАБОТАТЬ =================
@dp.message(F.text == "💎 Заработать")
async def referral(message: Message):
    link = f"https://t.me/{(await bot.get_me()).username}?start={message.from_user.id}"
    await message.answer(
        f"👥 Получай {REF_BONUS} RUB за каждого друга\n\n"
        f"🔗 Твоя ссылка:\n{link}"
    )

# ================= ИНФО =================
@dp.message(F.text == "ℹ️ Информация")
async def info(message: Message):
    await message.answer(
        "ℹ️ Информация\n"
        "━━━━━━━━━━━━\n"
        "💸 Минимальный вывод: 300 RUB\n"
        "👥 Пользователей: 14503\n"
        "💰 Общий баланс в боте: 345040 RUB\n"
        "📤 Выплачено: 69040 RUB\n"
    )

# ================= СУНДУК =================
@dp.message(F.text == "🔐 Сундук")
async def chest(message: Message):
    now = datetime.utcnow()
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT last_open FROM chest WHERE user_id=?", (message.from_user.id,)
        )
        row = await cur.fetchone()
        if row:
            last_open = datetime.fromisoformat(row[0])
            next_open = last_open + timedelta(hours=CHEST_COOLDOWN_HOURS)
            if now < next_open:
                remaining = next_open - now
                hours, remainder = divmod(int(remaining.total_seconds()), 3600)
                minutes = remainder // 60
                await message.answer(f"⏳ Сундук пока закрыт\nОсталось: {hours}ч {minutes}м")
                return
            await db.execute(
                "UPDATE chest SET last_open=? WHERE user_id=?",
                (now.isoformat(), message.from_user.id)
            )
        else:
            await db.execute(
                "INSERT INTO chest (user_id, last_open) VALUES (?, ?)",
                (message.from_user.id, now.isoformat())
            )
        await db.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id=?",
            (CHEST_REWARD, message.from_user.id)
        )
        await db.commit()

    await message.answer(f"🎉 Вы открыли сундук!\n💰 Получено: {CHEST_REWARD} RUB")

    # запускаем уведомление о готовности сундука
    cooldown_seconds = CHEST_COOLDOWN_HOURS * 3600
    asyncio.create_task(notify_chest_ready(message.from_user.id, cooldown_seconds))

async def notify_chest_ready(user_id: int, cooldown_seconds: int):
    await asyncio.sleep(cooldown_seconds)
    await bot.send_message(user_id, "🎉 Сундук снова готов! Можешь открыть его снова 💎")

# ================= ПРОМО =================
@dp.message(F.text == "✅ Активировать промокод")
async def promo_request(message: Message):
    await message.answer("✏️ Введите промокод")

@dp.message(F.text.regexp(r"^[A-Z0-9]{4,}$"))
async def activate_promo(message: Message):
    code = message.text.upper()
    async with aiosqlite.connect(DB_NAME) as db:
        promo = await db.execute_fetchone(
            "SELECT reward FROM promocodes WHERE code=? AND active=1", (code,)
        )
        used = await db.execute_fetchone(
            "SELECT 1 FROM promo_used WHERE user_id=? AND code=?",
            (message.from_user.id, code)
        )
        if not promo or used:
            await message.answer("❌ Промокод недействителен")
            return
        await db.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id=?",
            (promo[0], message.from_user.id)
        )
        await db.execute(
            "INSERT INTO promo_used VALUES (?, ?)",
            (message.from_user.id, code)
        )
        await db.commit()
    await message.answer(f"✅ Начислено {promo[0]} RUB")

# ================= ВЫВОД =================
@dp.message(F.text == "💸 Вывод средств")
async def withdraw(message: Message):
    user = await get_user(message.from_user.id)
    if user[2] < MIN_WITHDRAW:
        await message.answer(f"❌ Минимальная сумма вывода {MIN_WITHDRAW} RUB")
        return
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO withdraw_requests (user_id, amount, status) VALUES (?, ?, ?)",
            (message.from_user.id, user[2], "pending")
        )
        await db.commit()
    if WITHDRAW_MODE == "FAKE":
        await message.answer("💸 Заявка принята, ожидайте обработки (до 24 часов)")
    else:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "UPDATE users SET balance = 0, withdrawn = withdrawn + ? WHERE user_id=?",
                (user[2], message.from_user.id)
            )
            await db.commit()
        await message.answer("✅ Выплата отправлена")

# ================= АДМИН =================
@dp.message(F.text == "/admin")
async def admin(message: Message):
    if message.from_user.id in ADMINS:
        await message.answer("🔐 Админ-панель", reply_markup=admin_keyboard)

@dp.message(F.text == "⬅️ Назад")
async def back(message: Message):
    await message.answer("Главное меню", reply_markup=keyboard)

@dp.message(F.text == "📊 Статистика")
async def stats(message: Message):
    if message.from_user.id not in ADMINS:
        return
    users, balance, withdrawn = await get_stats()
    await message.answer(
        f"📊 Статистика\n👥 Пользователей: {users}\n💰 Общий баланс: {balance:.2f}\n📤 Выплачено: {withdrawn:.2f}"
    )

@dp.message(F.text == "🔁 Режим вывода")
async def switch_mode(message: Message):
    global WITHDRAW_MODE
    if message.from_user.id not in ADMINS:
        return
    WITHDRAW_MODE = "REAL" if WITHDRAW_MODE == "FAKE" else "FAKE"
    await message.answer(f"🔁 Режим вывода изменён\nТекущий режим: {WITHDRAW_MODE}")

@dp.message(F.text == "➕ Создать промокод")
async def promo_admin(message: Message):
    if message.from_user.id in ADMINS:
        await message.answer("Формат: PROMO10 10")

@dp.message(F.text.regexp(r"^[A-Z0-9]+ \d+(\.\d+)?$"))
async def create_promo(message: Message):
    if message.from_user.id not in ADMINS:
        return
    code, reward = message.text.split()
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO promocodes VALUES (?, ?, 1)", (code, float(reward)))
        await db.commit()
    await message.answer("✅ Промокод создан")

@dp.message(F.text == "📢 Рассылка")
async def mailing(message: Message):
    if message.from_user.id in ADMINS:
        await message.answer("✏️ Ответьте текстом на это сообщение")

@dp.message(F.reply_to_message & (F.from_user.id.in_(ADMINS)))
async def send_mailing(message: Message):
    async with aiosqlite.connect(DB_NAME) as db:
        users = await db.execute_fetchall("SELECT user_id FROM users")
    sent = 0
    for u in users:
        try:
            await bot.send_message(u[0], message.text)
            sent += 1
        except:
            pass
    await message.answer(f"📨 Отправлено: {sent}")

# ================= ЗАПУСК =================
async def main():
    logging.basicConfig(level=logging.INFO)
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
