import sqlite3
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# ==============================
# НАСТРОЙКИ
# ==============================
TOKEN = "8467227525:AAFDN01gp3iENMYWYBixYFFFToHFj2WXZBc"
ADMIN_ID = 8263725805
DB_FILE = "bot.db"
LOG_FILE = "bot.log"

# ==============================
# ЛОГИРОВАНИЕ
# ==============================
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ==============================
# БАЗА ДАННЫХ
# ==============================
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    contact TEXT NOT NULL,
    desc TEXT,
    file_id TEXT,
    timestamp TEXT NOT NULL
)
""")
conn.commit()

def save_order(name, contact, desc, file_id=None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO orders (name, contact, desc, file_id, timestamp) VALUES (?, ?, ?, ?, ?)",
        (name, contact, desc, file_id, timestamp)
    )
    conn.commit()
    logging.info(f"New order saved: {name}, {contact}, {desc}, file={file_id}")
    return cursor.lastrowid

def get_orders(limit=10):
    cursor.execute("SELECT id, name, contact, desc, file_id, timestamp FROM orders ORDER BY id DESC LIMIT ?", (limit,))
    return cursor.fetchall()

def delete_order(order_id):
    cursor.execute("DELETE FROM orders WHERE id=?", (order_id,))
    conn.commit()
    logging.info(f"Order deleted: {order_id}")

# ==============================
# /start
# ==============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📘 О боте", callback_data="about")],
        [InlineKeyboardButton("🛒 Услуги", callback_data="services")],
        [InlineKeyboardButton("📨 Оставить заявку", callback_data="order")],
        [InlineKeyboardButton("🆘 Помощь", callback_data="help")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Это демо-бот для обработки заявок🤖.\n"
        "Выберите действие в меню ниже.\n"
        "По жалобам: @Guglix",
        reply_markup=reply_markup
    )

# ==============================
# МЕНЮ
# ==============================
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "about":
        await query.message.reply_text("Это Junior-ready бот с SQLite, логами и CRUD для заявок.")
    elif query.data == "services":
        await query.message.reply_text("Наши услуги:\n• Telegram-боты\n• Автоматизация\n• Поддержка")
    elif query.data == "help":
        await query.message.reply_text("Напишите свой вопрос или нажмите «Оставить заявку».")
    elif query.data == "order":
        context.user_data["step"] = "name"
        await query.message.reply_text("Введите ваше имя:")

# ==============================
# ОБРАБОТКА ТЕКСТА И ФАЙЛОВ
# ==============================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get("step")
    text = update.message.text.strip() if update.message.text else ""

    if step == "name":
        if not text:
            await update.message.reply_text("Имя не может быть пустым, введите снова:")
            return
        context.user_data["name"] = text
        context.user_data["step"] = "contact"
        await update.message.reply_text("Введите контакт (Telegram или телефон):")
        return

    if step == "contact":
        if not text:
            await update.message.reply_text("Контакт не может быть пустым, введите снова:")
            return
        context.user_data["contact"] = text
        context.user_data["step"] = "desc"
        await update.message.reply_text("Кратко опишите запрос:")
        return

    if step == "desc":
        context.user_data["desc"] = text
        context.user_data["step"] = "file"
        await update.message.reply_text("Прикрепите файл/фото (если есть) или напишите 'нет':")
        return

    if step == "file":
        file_id = None
        if update.message.photo:
            file_id = update.message.photo[-1].file_id
        elif update.message.document:
            file_id = update.message.document.file_id

        save_order(
            name=context.user_data["name"],
            contact=context.user_data["contact"],
            desc=context.user_data["desc"],
            file_id=file_id
        )

        msg = (
            f"📨 Новая заявка:\n"
            f"Имя: {context.user_data['name']}\n"
            f"Контакт: {context.user_data['contact']}\n"
            f"Запрос: {context.user_data['desc']}"
        )
        if file_id:
            msg += "\n📎 Файл/Фото приложен"

        await context.bot.send_message(chat_id=ADMIN_ID, text=msg)
        await update.message.reply_text("✅ Заявка отправлена и сохранена.")
        context.user_data.clear()
        return

    # Сообщение вне заявки
    await update.message.reply_text(
        "Сообщение получено. Если хотите заказать услугу — нажмите «Оставить заявку»."
    )

# ==============================
# /orders и /delete_order
# ==============================
async def view_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("У вас нет доступа к заявкам.")
        return

    rows = get_orders(limit=10)
    if not rows:
        await update.message.reply_text("Заявок пока нет.")
        return

    msg = "📋 Последние заявки:\n\n"
    for row in rows:
        msg += f"{row[0]}. {row[1]} | {row[2]} | {row[3]} | {row[5]}\n"
    await update.message.reply_text(msg)

async def delete_order_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("У вас нет доступа.")
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Используйте: /delete_order <id>")
        return
    order_id = int(context.args[0])
    delete_order(order_id)
    await update.message.reply_text(f"Заявка {order_id} удалена.")

# ==============================
# ЗАПУСК БОТА
# ==============================
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("orders", view_orders))
    app.add_handler(CommandHandler("delete_order", delete_order_command))
    app.add_handler(CallbackQueryHandler(menu_handler))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.Document.ALL & ~filters.COMMAND, handle_text))

    print("🤖 Junior-ready бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()