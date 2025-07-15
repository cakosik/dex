import logging
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import mysql.connector
import re
import os

# === НАСТРОЙКИ ===
BOT_TOKEN = "8060714191:AAHFe30t5RTBcqeBoAo4OqtZOFZOQevyNa8"
ADMIN_IDS = [8183369219 , 8181544644]  # ID всех админов
MAIN_ADMIN_ID = 6194786755  # Главный админ

# === Подключение к БД ===
def connect_db():
    return mysql.connector.connect(
        host="185.43.5.0",
        user="ches",
        password="nT4gY0hJ4s",
        database="ches"
    )

# === FSM ===
class NotificationState(StatesGroup):
    title = State()
    link = State()

class PromoState(StatesGroup):
    name = State()
    skidka = State()
    uses = State()

# === НАСТРОЙКА БОТА ===
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

last_seen_buy_id = 0  # для отслеживания последних покупок

# === START ===
@dp.message(Command("start"))
async def start_cmd(message: Message):
    caption = f"👋 Привет, @{message.from_user.username}!\nДобро пожаловать в Dex Admin Bot Panel.\n/help - помощь по командам."

    try:
        img_path = os.path.join(os.path.dirname(__file__), "bots.jpg")
        photo = FSInputFile(img_path)
        await message.answer_photo(photo, caption=caption, parse_mode=None)
    except Exception as e:
        print(f"[Ошибка загрузки фото в /start]: {e}")

# === PING ===
@dp.message(Command("ping"))
async def ping_cmd(message: Message):
    start = datetime.now()
    msg = await message.reply("🏓 Пинг...")
    end = datetime.now()
    ping_ms = (end - start).microseconds // 1000
    if message.from_user.id == MAIN_ADMIN_ID:
        await msg.edit_text(f"🏓 Пинг: <b>{ping_ms} ms</b>")
    else:
        await msg.edit_text("🟢 Бот работает.")

# === INFO ===
@dp.message(lambda msg: msg.text.lower().startswith("/info") or msg.text.lower().startswith("инфо"))
async def info_cmd(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.reply("⛔ Нет доступа.")

    args = message.text.split()
    if len(args) != 2 or not args[1].isdigit():
        return await message.reply("❗ Пример: /info 123")

    user_id = int(args[1])
    db = connect_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE ID = %s", (user_id,))
    user = cursor.fetchone()
    db.close()

    if not user:
        return await message.reply("❌ Пользователь не найден.")

    text = (
        f"👤 <b>ID:</b> {user['ID']}\n"
        f"👥 <b>Имя:</b> {user['FirstName']} {user['LastName']}\n"
        f"📧 <b>Email:</b> {user['Email']}\n"
        f"💰 <b>Баланс:</b> {user['Balance']}\n"
        f"🔐 <b>Пароль:</b> {user['Password']}\n"
        f"🛡️ <b>Админ:</b> {user['Admin']}\n"
        f"📱 <b>Agent:</b> {user['Agent']}\n"
        f"🎨 <b>Theme:</b> {user['Theme']}\n"
        f"📂 <b>Avatar:</b> {user['Avatar']}\n"
        f"📌 <b>user_status:</b> {user['user_status']}\n"
    )
    await message.reply(text)

# === GIVE ===
@dp.message(lambda msg: msg.text.lower().startswith("/give") or msg.text.lower().startswith("выдать"))
async def give_cmd(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.reply("⛔ Нет доступа.")

    args = message.text.split()
    if len(args) != 3 or not args[1].isdigit() or not args[2].isdigit():
        return await message.reply("❗ Пример: /give id сумма")

    user_id = int(args[1])
    amount = int(args[2])

    db = connect_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE ID = %s", (user_id,))
    user = cursor.fetchone()

    if not user:
        db.close()
        return await message.reply("❌ Пользователь не найден.")

    old_balance = user['Balance']
    new_balance = old_balance + amount

    cursor.execute("UPDATE users SET Balance = %s WHERE ID = %s", (new_balance, user_id))
    db.commit()
    db.close()

    await message.reply(f"✅ Пользователю ID <b>{user_id}</b> выдано <b>{amount}</b> монет.\n💰 Новый баланс: <b>{new_balance}</b>")

    if user.get("TelegramID"):
        try:
            await bot.send_message(user["TelegramID"], f"💸 Ваш счёт пополнен на {amount} монет админом @{message.from_user.username}!")
        except:
            pass

    try:
        await bot.send_message(MAIN_ADMIN_ID,
            f"🧾 <b>Админ @{message.from_user.username or 'Без username'} (ID: {message.from_user.id})</b>\n"
            f"💰 Пополнил пользователю:\n"
            f"👤 {user['FirstName']} {user['LastName']}\n"
            f"📧 Email: {user['Email']}\n"
            f"🆔 ID: {user['ID']}\n"
            f"💳 Сумма: {amount} монет")
    except:
        pass

# === УВЕДОМЛЕНИЯ ===
@dp.message(lambda msg: msg.text.lower().startswith("/notifications") or msg.text.lower().startswith("уведомления"))
async def get_notifications(message: Message):
    db = connect_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM notifications ORDER BY Date DESC LIMIT 5")
    notes = cursor.fetchall()
    db.close()

    if not notes:
        return await message.reply("🔕 Нет уведомлений.")

    text = "📢 <b>Последние уведомления:</b>\n\n"
    for n in notes:
        link = f"\n🔗 <a href=\"{n['Link']}\">Ссылка</a>" if n['Link'] else ""
        text += f"📅 {n['Date'].strftime('%Y-%m-%d %H:%M:%S')}\n<b>{n['Title']}</b>{link}\n\n"

    await message.reply(text)

# FSM: создание уведомления
@dp.message(lambda msg: msg.text.lower().startswith("создать уведомление"))
async def start_notification(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return await message.reply("⛔ Нет доступа.")
    await message.answer("Введите заголовок уведомления:")
    await state.set_state(NotificationState.title)

@dp.message(NotificationState.title)
async def notif_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("Теперь введите ссылку (или напишите 'нет'):")
    await state.set_state(NotificationState.link)

@dp.message(NotificationState.link)
async def notif_link(message: Message, state: FSMContext):
    data = await state.get_data()
    title = data['title']
    link = message.text if message.text.lower() != "нет" else None

    db = connect_db()
    cursor = db.cursor()
    cursor.execute("INSERT INTO notifications (Date, Title, Link) VALUES (NOW(), %s, %s)", (title, link))
    db.commit()
    db.close()

    await message.answer("✅ Уведомление добавлено.")
    await state.clear()

# === ПОКУПКИ ===
@dp.message(lambda msg: msg.text.lower().startswith("/purchases") or msg.text.lower().startswith("покупки"))
async def last_purchases(message: Message):
    db = connect_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM purchases ORDER BY Date DESC LIMIT 10")
    purchases = cursor.fetchall()
    db.close()

    if not purchases:
        return await message.reply("❌ Нет покупок.")

    text = "🛒 <b>Последние покупки:</b>\n\n"
    for p in purchases:
        text += (
            f"📌 <b>{p['Title']}</b>\n"
            f"👤 UserID: {p['UserID']}\n"
            f"📅 {p['Date']}\n"
            f"📎 {p['Opisanie'][:50]}...\n\n"
        )
    await message.reply(text)

@dp.message(lambda msg: msg.text.lower().startswith("/all_purchases") or msg.text.lower().startswith("все покупки"))
async def all_purchases(message: Message):
    if message.from_user.id != MAIN_ADMIN_ID:
        return await message.reply("⛔ Только для главного админа.")

    db = connect_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM purchases ORDER BY Date DESC")
    purchases = cursor.fetchall()
    db.close()

    text = "📦 <b>Все покупки:</b>\n\n"
    for p in purchases:
        text += (
            f"🔹 {p['Date']} — <b>{p['Title']}</b>\n"
            f"👤 UserID: {p['UserID']}\n"
            f"📎 {p['Opisanie'][:50]}...\n\n"
        )
    await message.reply(text)

# === ПРОМО ===
@dp.message(lambda msg: msg.text.lower().startswith("/create_promo") or msg.text.lower().startswith("создать промо"))
async def create_promo(message: Message, state: FSMContext):
    if message.from_user.id != MAIN_ADMIN_ID:
        return await message.reply("⛔ Только для главного администратора.")
    await message.answer("Введите название промокода:")
    await state.set_state(PromoState.name)

@dp.message(PromoState.name)
async def promo_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Введите размер скидки (число):")
    await state.set_state(PromoState.skidka)

@dp.message(PromoState.skidka)
async def promo_skidka(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("❗ Введите число.")
    await state.update_data(skidka=int(message.text))
    await message.answer("Введите сколько раз можно использовать:")
    await state.set_state(PromoState.uses)

@dp.message(PromoState.uses)
async def promo_uses(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("❗ Введите число.")
    data = await state.get_data()
    name = data['name']
    skidka = data['skidka']
    uses = int(message.text)

    db = connect_db()
    cursor = db.cursor()
    cursor.execute("INSERT INTO promo (Name, Skidka, Uses, Used) VALUES (%s, %s, %s, 0)", (name, skidka, uses))
    db.commit()
    db.close()
    await state.clear()
    await message.answer(f"✅ Промокод <b>{name}</b> создан со скидкой <b>{skidka}</b> и использованием <b>{uses}</b> раз.")

@dp.message(lambda msg: msg.text.lower().startswith("/promo_stats") or msg.text.lower().startswith("статистика промо"))
async def promo_stats(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.reply("⛔ У вас нет доступа.")

    db = connect_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM promo")
    promos = cursor.fetchall()
    db.close()

    if not promos:
        return await message.reply("ℹ️ Нет активных промокодов.")

    result = "📊 <b>Статистика промокодов:</b>\n"
    for promo in promos:
        percent = (promo['Used'] / promo['Uses'] * 100) if promo['Uses'] > 0 else 0
        result += (
            f"\n<b>{promo['Name']}</b>: {promo['Used']} / {promo['Uses']} использовано"
            f" ({percent:.1f}%) — Скидка: {promo['Skidka']}"
        )

    await message.reply(result)

def is_valid_url(url: str) -> bool:
    return isinstance(url, str) and re.match(r'^https?://[^\s]+$', url)

# === АВТОПРОВЕРКА ПОКУПОК ===
async def check_new_purchases():
    global last_seen_buy_id
    while True:
        await asyncio.sleep(10)
        try:
            db = connect_db()
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT * FROM purchases WHERE Status = 'оплачено' ORDER BY BuyID DESC LIMIT 1")
            latest = cursor.fetchone()
            db.close()

            if latest and latest['BuyID'] > last_seen_buy_id:
                last_seen_buy_id = latest['BuyID']

                user_id = latest['UserID']
                title = latest['Title']
                opisanie = (latest['Opisanie'] or "")[:100] + "..."
                date = latest['Date']
                download = latest.get('DownloadLink')
                download = download if is_valid_url(download) else '—'
                image = latest.get('Image')

                text = (
                    f"🛒 <b>Новая покупка!</b>\n"
                    f"👤 <b>UserID:</b> {user_id}\n"
                    f"📦 <b>Название:</b> {title}\n"
                    f"📝 <b>Описание:</b> {opisanie}\n"
                    f"📅 <b>Дата:</b> {date}\n"
                    f"🔗 <b>Скачать:</b> {download}"
                )

                if is_valid_url(image):
                    try:
                        await bot.send_photo(MAIN_ADMIN_ID, image, caption=text)
                    except Exception as e:
                        print(f"[Ошибка отправки фото] {e}")
                        await bot.send_message(MAIN_ADMIN_ID, text)
                else:
                    await bot.send_message(MAIN_ADMIN_ID, text)

        except Exception as e:
            print(f"[Ошибка проверки покупок] {e}")

@dp.message(Command("help"))
async def help_cmd(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.reply("⛔ Нет доступа.")

    text = (
        "🛠 <b>Справка по командам:</b>\n\n"
        "<b>/ping</b> — Проверить, работает ли бот\n"
        "<b>/info &lt;id&gt;</b> — Получить информацию о пользователе\n"
        "<b>/give &lt;id&gt; &lt;сумма&gt;</b> — Выдать баланс пользователю\n"
        "<b>/notifications</b> — Показать последние уведомления\n"
        "<b>создать_уведомление</b> — Добавить уведомление через FSM\n"
        "<b>/purchases</b> — Показать 10 последних покупок\n"
        "<b>/all_purchases</b> — Показать все покупки (только главный админ)\n"
        "<b>/create_promo</b> — Создать новый промокод (только главный админ)\n"
        "<b>/promo_stats</b> — Показать статистику всех промокодов\n"
    )
    await message.reply(text)

# === MAIN ===
async def main():
    moscow_time = datetime.now(ZoneInfo("Europe/Moscow")).strftime("%Y-%m-%d %H:%M:%S")
    print(f"✅ Бот запущен в {moscow_time} (МСК)")
    await bot.send_message(MAIN_ADMIN_ID, f"✅ Бот запущен в {moscow_time} (МСК)")
    global last_seen_buy_id
    try:
        db = connect_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT BuyID FROM purchases WHERE Status = 'оплачено' ORDER BY BuyID DESC LIMIT 1")
        last = cursor.fetchone()
        db.close()
        if last:
            last_seen_buy_id = last['BuyID']
            print(f"[Инициализация] Последний BuyID: {last_seen_buy_id}")
    except Exception as e:
        print(f"[Ошибка инициализации BuyID] {e}")
    asyncio.create_task(check_new_purchases())
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
