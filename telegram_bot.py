import os
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
from main import run_dev_team
from history import load_history

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER_ID = int(os.getenv("TELEGRAM_ALLOWED_USER_ID", "0"))

def is_allowed(update: Update) -> bool:
    return update.effective_user.id == ALLOWED_USER_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    await update.message.reply_text(
        "👋 Привет! Я твоя команда ИИ-разработчиков.\n\n"
        "Просто напиши задачу — и агенты возьмутся за работу.\n\n"
        "Команды:\n"
        "/history — последние 5 задач\n"
        "/start — это сообщение"
    )

async def history_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    runs = load_history()
    if not runs:
        await update.message.reply_text("История пуста. Дай первую задачу!")
        return
    lines = []
    for run in runs[-5:]:
        status = "✅" if run["approved"] else "⚠️"
        lines.append(f"{status} {run['date'][:16]}\n   {run['task'][:50]}")
    await update.message.reply_text("Последние задачи:\n\n" + "\n\n".join(lines))

async def handle_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        await update.message.reply_text("⛔ Доступ запрещён.")
        return

    task = update.message.text
    await update.message.reply_text(
        f"⚙️ Принято! Агенты работают над задачей...\n\n_{task}_",
        parse_mode="Markdown"
    )

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, run_dev_team, task)

        status = "✅ Код одобрен ревьюером" if result["approved"] else "⚠️ Код требует доработки"
        iterations = result.get("iterations", 1)

        summary = (
            f"{status}\n"
            f"Итераций: {iterations}\n\n"
            f"*План:*\n{result['plan'][:500]}...\n\n"
            f"*Код готов.* Полный результат сохранён в историю."
        )
        await update.message.reply_text(summary, parse_mode="Markdown")

        code_preview = result["code"][:2000]
        await update.message.reply_text(f"```python\n{code_preview}\n```", parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("history", history_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_task))
    print("🤖 Telegram бот запущен. Ctrl+C для остановки.")
    app.run_polling()

if __name__ == "__main__":
    main()
