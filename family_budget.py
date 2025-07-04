import logging
from telegram import Update, ReplyKeyboardMarkup, BotCommand
from telegram.ext import (ApplicationBuilder, CommandHandler, ContextTypes,
                          ConversationHandler, MessageHandler, filters)
import datetime
import gspread
import json
import os
from oauth2client.service_account import ServiceAccountCredentials
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from collections import defaultdict

# ============ CONFIG LOAD ============
config = json.loads(os.getenv("BOT_CONFIG_JSON"))
print("BOT_CONFIG_JSON:", os.getenv("BOT_CONFIG_JSON"))

TOKEN = config['telegram_token']
ALLOWED_USERS = config.get('allowed_user_ids', [])
SPREADSHEET_ID = config.get('sheet_name', '1y039e2_zew51s0kQFUijIiX6_bq29Jx4U-7upo1nTts')

# ============ GOOGLE SHEETS INIT ============
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]
creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(creds_json), scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).sheet1

# ============ CONSTANTS ============
CATEGORY, AMOUNT, COMMENT = range(3)

CATEGORIES = [
    "Оренда", "Інвестиції", "Няня/Садок", "Накопичення",
    "Харчування + Побут/гігієна", "Шопінг", "Розваги/заклади",
    "Спорт", "Медецина", "Авто(бенз)",
    "Резерв непередбачування"
]

CATEGORY_LIMITS = {
    "Оренда": 8000,
    "Інвестиції": 2522,
    "Няня/Садок": 4000,
    "Накопичення": 10600,
    "Харчування + Побут/гігієна": 2170,
    "Шопінг": 742,
    "Розваги/заклади": 1060,
    "Медецина": 870,
    "Спорт": 244,
    "Авто(бенз)": 708,
    "Резерв непередбачування": 1272,
}

# ============ HELPERS ============
def get_total_expenses_per_category(category):
    records = sheet.get_all_records()
    total = sum(float(row['Сума']) for row in records if row['Категорія'] == category)
    return total

def get_main_menu():
    keyboard = [
        ["💰 Баланс"],
        ["➕ Додати витрату", "📊 Статистика"],
        ["📅 Звіт за сьогодні"],
        ["❌ Скасувати"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_category_keyboard():
    keyboard = []
    row = []
    for i, cat in enumerate(CATEGORIES, 1):
        row.append(cat)
        if i % 2 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append(["🔙 Назад"])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

# ============ BOT LOGIC ============
logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if ALLOWED_USERS and user.id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ У вас немає доступу до цього бота.")
        return ConversationHandler.END

    await update.message.reply_text("Оберіть дію:", reply_markup=get_main_menu())
    return ConversationHandler.END

async def start_expense_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Оберіть категорію:", reply_markup=get_category_keyboard())
    return CATEGORY

async def category_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    category = update.message.text
    if category == "🔙 Назад":
        await update.message.reply_text("Оберіть дію:", reply_markup=get_main_menu())
        return ConversationHandler.END
    if category not in CATEGORIES:
        await update.message.reply_text("❗ Оберіть категорію з клавіатури.")
        return CATEGORY
    context.user_data['category'] = category
    await update.message.reply_text(f"Категорія: {category}\nВведіть суму витрати (в zł):")
    return AMOUNT

async def amount_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.replace(',', '.'))
        context.user_data['amount'] = amount
        await update.message.reply_text("Введіть коментар (або '-' якщо немає):")
        return COMMENT
    except ValueError:
        await update.message.reply_text("❗ Введіть число.")
        return AMOUNT

async def comment_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    comment = update.message.text
    category = context.user_data.get('category')
    amount = context.user_data.get('amount')
    username = update.message.from_user.first_name
    date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    sheet.append_row([date_str, username, category, amount, comment])

    spent = get_total_expenses_per_category(category)
    limit = CATEGORY_LIMITS.get(category, 0)
    remaining = limit - spent
    percent = (spent / limit) * 100 if limit > 0 else 0

    await update.message.reply_text(
        f"✅ Витрату додано:\nКатегорія: {category} = {amount:.2f} zł\n"
        f"{limit:.0f} / {spent:.2f} → Залишок: {remaining:.2f} zł ({100 - percent:.0f}%)",
        reply_markup=get_main_menu()
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Скасовано", reply_markup=get_main_menu())
    return ConversationHandler.END

async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = "\U0001F4C8 Баланс категорій:\n"
    for cat in CATEGORIES:
        spent = get_total_expenses_per_category(cat)
        limit = CATEGORY_LIMITS.get(cat, 0)
        remaining = limit - spent
        percent = (spent / limit * 100) if limit else 0
        message += f"• {cat}: {spent:.2f} / {limit} → Залишок: {remaining:.2f} zł ({100 - percent:.0f}%)\n"
    await update.message.reply_text(message, reply_markup=get_main_menu())

async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.datetime.now()
    month_start = datetime.datetime(now.year, now.month, 1)
    records = sheet.get_all_records()
    month_records = [r for r in records if datetime.datetime.strptime(r['Дата'], "%Y-%m-%d %H:%M") >= month_start]

    totals = defaultdict(float)
    for row in month_records:
        totals[row['Категорія']] += float(row['Сума'])

    message = f"📊 Статистика за {now.strftime('%B %Y')}\n"
    for cat in CATEGORIES:
        spent = totals.get(cat, 0)
        limit = CATEGORY_LIMITS.get(cat, 0)
        percent = (spent / limit) * 100 if limit > 0 else 0
        message += f"• {cat}: {spent:.2f} / {limit} zł ({percent:.0f}%)\n"

    # Top-3 categories
    top = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:3]
    message += "\n🏆 Топ-3 категорії за витратами:\n"
    for cat, val in top:
        message += f"{cat}: {val:.2f} zł\n"

    await update.message.reply_text(message, reply_markup=get_main_menu())

async def send_daily_report(context: ContextTypes.DEFAULT_TYPE, manual_user_id=None):
    now_date = datetime.datetime.now().strftime("%Y-%m-%d")
    records = sheet.get_all_records()
    today_records = [r for r in records if r['Дата'].startswith(now_date)]

    if not today_records:
        return

    # First message: all expenses of the day
    lines = [f"📅 Витрати за {now_date}:"]
    for row in today_records:
        lines.append(f"• {row['Сума']} zł – {row['Категорія']} ({row['Користувач']})")
    report_text_1 = "\n".join(lines)

    # Second message: total per category and total
    totals = defaultdict(float)
    for row in today_records:
        totals[row['Категорія']] += float(row['Сума'])
    total_sum = sum(totals.values())
    report_lines = ["📊 Підсумок по категоріях:"]
    for cat, val in totals.items():
        report_lines.append(f"• {cat}: {val:.2f} zł")
    report_lines.append(f"\n💸 Загальні витрати за день: {total_sum:.2f} zł")
    report_text_2 = "\n".join(report_lines)

    targets = [manual_user_id] if manual_user_id else ALLOWED_USERS
    for user_id in targets:
        try:
            await context.bot.send_message(chat_id=user_id, text=report_text_1)
            await context.bot.send_message(chat_id=user_id, text=report_text_2)
        except Exception as e:
            logging.warning(f"Не вдалося надіслати звіт користувачу {user_id}: {e}")

async def manual_daily_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_daily_report(context, manual_user_id=update.effective_user.id)

# ============ MAIN ============
def main():
    application = ApplicationBuilder().token(TOKEN).build()

    async def post_init(app):
        await app.bot.set_my_commands([
            BotCommand("start", "Запустити бота / головне меню"),
            BotCommand("balance", "Переглянути баланс"),
            BotCommand("add", "Додати витрату"),
            BotCommand("cancel", "Скасувати дію"),
            BotCommand("stats", "Статистика за місяць"),
            BotCommand("report", "Звіт за день")
        ])
        scheduler.start()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_report, 'cron', hour=21, minute=0, args=[application.bot])

    application.post_init = post_init

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^➕ Додати витрату$"), start_expense_add)
        ],
        states={
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, category_chosen)],
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, amount_entered)],
            COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, comment_entered)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Скасувати$"), cancel)],
        allow_reentry=True,
        per_message=False,
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("report", manual_daily_report))
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.Regex("^💰 Баланс$"), show_balance))
    application.add_handler(MessageHandler(filters.Regex("^📊 Статистика$"), show_statistics))
    application.add_handler(MessageHandler(filters.Regex("^📅 Звіт за сьогодні$"), manual_daily_report))

    application.run_polling()

if __name__ == '__main__':
    main()
