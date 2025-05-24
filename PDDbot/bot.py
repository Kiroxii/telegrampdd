import os
import json
import re
import random
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)



load_dotenv()  # Загружает переменные из .env
TOKEN = os.getenv("TOKEN")  # Получает токен

# Режимы работы
MODES = {
    "exam": {
        "name": "Экзамен",
        "questions": 20,
        "description": "Режим как на реальном экзамене (20 вопросов)",
    },
    "express": {
        "name": "Экспресс",
        "questions": 10,
        "description": "Быстрая проверка знаний (10 случайных вопросов)",
    },
    "marathon": {
        "name": "Марафон",
        "questions": 100,
        "description": "Все билеты подряд (100 вопросов)",
    },
}


class UserState:
    def __init__(self):
        self.current_mode = "exam"
        self.current_ticket = 1
        self.current_question = 0
        self.score = 0
        self.answers_history = []
        self.questions_order = []


users_state = {}


def get_user_state(user_id):
    if user_id not in users_state:
        users_state[user_id] = UserState()
    return users_state[user_id]


def load_tickets():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Ошибка загрузки данных: {e}")
        return []


tickets_data = load_tickets()


def clean_text(text):
    """Очистка текста от лишних символов и форматирования"""
    if not text:
        return ""

    # Удаляем HTML-теги
    text = re.sub(r"<[^>]+>", "", text)
    # Удаляем дублирование номеров (например "1. 1. Текст" -> "1. Текст")
    text = re.sub(r"(\d+)\.\s*\1\.?", r"\1.", text)
    # Удаляем лишние пробелы
    text = " ".join(text.split())
    # Форматируем пункты ПДД
    text = re.sub(r"(Пункт)(\d+\.\d+)", r"\1 \2", text)
    return text


def clean_explanation(explanation):
    """Очистка объяснения - оставляем только текст и пункты ПДД"""
    if not explanation:
        return ""

    # Удаляем "Правильный ответ" и "Вопрос №" части
    explanation = re.sub(r"Правильный ответ:.*$", "", explanation, flags=re.MULTILINE)
    explanation = re.sub(r"Вопрос №.*$", "", explanation, flags=re.MULTILINE)

    # Удаляем HTML-теги
    explanation = re.sub(r"<[^>]+>", "", explanation)

    # Добавляем пробелы между пунктами ПДД и текстом
    explanation = re.sub(r"(\d+\.\d+)([А-Яа-я])", r"\1 \2", explanation)
    explanation = re.sub(r"([А-Яа-я])(\d+\.\d+)", r"\1 \2", explanation)

    # Форматируем знаки ПДД (добавляем пробелы и переносы)
    explanation = re.sub(r"([А-Яа-я])-(\d+\.\d+)", r"\1 - \2", explanation)
    explanation = re.sub(r"([А-Яа-я])(«)", r"\1 \2", explanation)
    explanation = re.sub(r"(»)([А-Яа-я])", r"\1 \2", explanation)

    # Разбиваем на предложения и добавляем переносы
    sentences = [
        s.strip() for s in re.split(r"(?<=[.!?])\s+", explanation) if s.strip()
    ]
    explanation = "\n\n".join(sentences)

    # Добавляем отступы перед пунктами
    explanation = re.sub(r"(Пункт \d+\.\d+ ПДД)", r"\n🔹 \1\n", explanation)

    return explanation


def get_next_question(state):
    """Получение следующего вопроса в зависимости от режима"""
    if state.current_mode == "exam":
        ticket = next(
            (
                t
                for t in tickets_data
                if int(t["ticket_number"]) == state.current_ticket
            ),
            None,
        )
        if ticket and state.current_question < len(ticket["questions"]):
            return ticket["questions"][state.current_question]

    elif state.current_mode in ["express", "marathon"]:
        if not state.questions_order:
            all_questions = []
            for ticket in tickets_data:
                all_questions.extend(ticket["questions"])
            random.shuffle(all_questions)
            state.questions_order = all_questions[
                : MODES[state.current_mode]["questions"]
            ]

        if state.current_question < len(state.questions_order):
            return state.questions_order[state.current_question]
    return None


def get_current_question(state):
    """Возвращает текущий вопрос"""
    if state.current_mode == "exam":
        ticket = next(
            (
                t
                for t in tickets_data
                if int(t["ticket_number"]) == state.current_ticket
            ),
            None,
        )
        if ticket and state.current_question < len(ticket["questions"]):
            return ticket["questions"][state.current_question]
    elif state.current_mode in ["express", "marathon"]:
        if state.questions_order and state.current_question < len(
            state.questions_order
        ):
            return state.questions_order[state.current_question]
    return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    help_text = """
🚗 <b>Добро пожаловать в бота для подготовки к ПДД!</b>

📝 <b>Доступные команды:</b>
/exam - Полный билет (20 вопросов)
/express - Экспресс-тест (10 вопросов) 
/marathon - Марафон (100 вопросов)
/ticket - Выбрать конкретный билет
/stats - Ваша статистика
/help - Помощь

📌 <b>Режимы тестирования:</b>
"""
    for mode, info in MODES.items():
        help_text += f"- <i>{info['name']}</i>: {info['description']}\n"

    keyboard = [
        [InlineKeyboardButton("📚 Начать экзамен", callback_data="mode_exam")],
        [InlineKeyboardButton("⚡ Экспресс-тест", callback_data="mode_express")],
        [InlineKeyboardButton("🏁 Марафон", callback_data="mode_marathon")],
        [InlineKeyboardButton("🔎 Выбрать билет", callback_data="select_ticket")],
    ]
    await update.message.reply_text(
        help_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
    )


async def exam_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /exam"""
    user_id = update.effective_user.id
    state = get_user_state(user_id)
    state.current_mode = "exam"
    await start_exam(update, context)


async def express_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /express"""
    user_id = update.effective_user.id
    state = get_user_state(user_id)
    state.current_mode = "express"
    await start_exam(update, context)


async def marathon_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /marathon"""
    user_id = update.effective_user.id
    state = get_user_state(user_id)
    state.current_mode = "marathon"
    await start_exam(update, context)


async def set_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установка режима тестирования"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    state = get_user_state(user_id)
    mode = query.data.split("_")[1]
    state.current_mode = mode
    state.current_question = 0
    state.score = 0
    state.answers_history = []
    state.questions_order = []

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Выбран режим: <b>{MODES[mode]['name']}</b>\n{MODES[mode]['description']}",
        parse_mode="HTML",
    )
    await start_exam(update, context)


async def select_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор билета для тестирования"""
    query = update.callback_query
    await query.answer()

    # Создаем клавиатуру с билетами (группируем по 5 в ряд)
    keyboard = []
    row = []
    for i in range(1, 41):  # 40 билетов
        row.append(InlineKeyboardButton(f"Билет {i}", callback_data=f"ticket_{i}"))
        if len(row) == 5:
            keyboard.append(row)
            row = []
    if row:  # Добавляем оставшиеся кнопки
        keyboard.append(row)

    # Добавляем кнопку возврата
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])

    await query.edit_message_text(
        text="📚 Выберите билет для решения:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def set_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установка выбранного билета"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    state = get_user_state(user_id)
    ticket_number = int(query.data.split("_")[1])

    state.current_ticket = ticket_number
    state.current_mode = "exam"  # Режим экзамена по конкретному билету
    state.current_question = 0
    state.score = 0
    state.answers_history = []
    state.questions_order = []

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Выбран билет №{ticket_number}. Начинаем тестирование!",
        parse_mode="HTML",
    )
    await start_exam(update, context)


async def start_exam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало тестирования"""
    user_id = update.effective_user.id
    state = get_user_state(user_id)

    state.current_question = 0
    state.score = 0
    state.answers_history = []

    await show_question(update, context)


async def show_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отображение вопроса"""
    user_id = update.effective_user.id
    state = get_user_state(user_id)

    question = get_next_question(state)
    if not question:
        await finish_exam(update, context)
        return

    # Формируем текст с вариантами ответов
    answers_text = "\n".join(
        [
            f"{i}. {clean_text(answer['text']).lstrip(f'{i}.').strip()}"
            for i, answer in enumerate(question["answers"], 1)
        ]
    )

    # Создаем кнопки
    keyboard = [
        [
            InlineKeyboardButton(
                str(i), callback_data=f"answer_{i-1}_{state.current_question}"
            )
            for i in range(1, len(question["answers"]) + 1)
        ],
        [
            InlineKeyboardButton("⏭ Пропустить", callback_data="skip_question"),
            InlineKeyboardButton("❌ Отменить тест", callback_data="cancel_exam"),
        ],
    ]

    question_text = (
        f"📌 Вопрос {state.current_question + 1}/{MODES[state.current_mode]['questions']}\n"
        f"────────────────────\n"
        f"{clean_text(question['question_text'])}\n\n"
        f"🔹 Сложность: {question.get('error_rate', 'неизвестно')}\n\n"
        f"<b>Варианты ответов:</b>\n"
        f"{answers_text}"
    )

    # Отправка вопроса
    if question.get("image"):
        try:
            with open(os.path.join("data", question["image"]), "rb") as photo:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=photo,
                    caption=question_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="HTML",
                )
        except Exception as e:
            print(f"Ошибка изображения: {e}")
            await send_question(update, context, question_text, keyboard)
    else:
        await send_question(update, context, question_text, keyboard)


async def send_question(
    update: Update, context: ContextTypes.DEFAULT_TYPE, text, keyboard
):
    """Вспомогательная функция для отправки вопроса"""
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ответа пользователя"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    state = get_user_state(user_id)

    if query.data.startswith("skip_question"):
        await handle_skip_question(update, context)
        return

    _, answer_idx, _ = query.data.split("_")
    answer_idx = int(answer_idx)

    question = get_current_question(state)
    is_correct = question["answers"][answer_idx]["is_correct"]
    state.answers_history.append((state.current_question + 1, is_correct))

    if is_correct:
        state.score += 1
        feedback = "✅ <b>Правильно!</b>"
    else:
        feedback = (
            "❌ <b>Ошибка!</b>\n\n"
            f"📘 <b>Объяснение:</b>\n{clean_explanation(question['explanation'])}"
        )

    await context.bot.send_message(
        chat_id=update.effective_chat.id, text=feedback, parse_mode="HTML"
    )

    state.current_question += 1
    if state.current_question < MODES[state.current_mode]["questions"]:
        await show_question(update, context)
    else:
        await finish_exam(update, context)


async def handle_skip_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пропуск вопроса"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    state = get_user_state(user_id)

    state.current_question += 1
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="⏭ <b>Вопрос пропущен</b>",
        parse_mode="HTML",
    )
    await show_question(update, context)


async def cancel_exam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Досрочное завершение теста"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    state = get_user_state(user_id)

    correct = sum(1 for _, correct in state.answers_history if correct)
    total = len(state.answers_history)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Тест прерван. Ваш результат: {correct}/{total} правильных ответов",
        parse_mode="HTML",
    )

    # Сбрасываем состояние
    state.current_question = 0
    state.score = 0
    state.answers_history = []
    state.questions_order = []

    await start(query, context)


async def finish_exam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершение теста"""
    user_id = update.effective_user.id
    state = get_user_state(user_id)

    result_text = (
        f"📊 <b>Результаты {MODES[state.current_mode]['name']}:</b>\n"
        f"────────────────────\n"
        f"✅ <b>Правильных:</b> {state.score}/{MODES[state.current_mode]['questions']}\n"
        f"📈 <b>Процент:</b> {state.score/MODES[state.current_mode]['questions']*100:.1f}%\n\n"
    )

    if state.score / MODES[state.current_mode]["questions"] < 0.7:
        result_text += "🔻 <b>Нужно повторить материал!</b>"
    else:
        result_text += "🔹 <b>Отличный результат!</b>"

    keyboard = [
        [
            InlineKeyboardButton(
                "🔄 Повторить", callback_data=f"mode_{state.current_mode}"
            ),
            InlineKeyboardButton("📚 Главное меню", callback_data="main_menu"),
        ],
        [
            InlineKeyboardButton(
                "⚡ Выбрать другой режим", callback_data="select_mode"
            ),
            InlineKeyboardButton("🔎 Выбрать билет", callback_data="select_ticket"),
        ],
    ]

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=result_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню"""
    query = update.callback_query
    await query.answer()
    await start(query, context)


async def select_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор режима тестирования"""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("📚 Экзамен (20 вопросов)", callback_data="mode_exam")],
        [
            InlineKeyboardButton(
                "⚡ Экспресс (10 вопросов)", callback_data="mode_express"
            )
        ],
        [
            InlineKeyboardButton(
                "🏁 Марафон (100 вопросов)", callback_data="mode_marathon"
            )
        ],
        [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")],
    ]

    await query.edit_message_text(
        text="Выберите режим тестирования:", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    await start(update, context)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /stats"""
    user_id = update.effective_user.id
    state = get_user_state(user_id)

    stats_text = (
        f"📊 <b>Ваша статистика:</b>\n"
        f"────────────────────\n"
        f"🔹 Текущий режим: {MODES[state.current_mode]['name']}\n"
        f"🔹 Правильных ответов: {state.score}\n"
        f"🔹 Всего вопросов: {len(state.answers_history)}\n"
    )

    if state.answers_history:
        correct = sum(1 for _, correct in state.answers_history if correct)
        stats_text += (
            f"🔹 Процент правильных: {correct/len(state.answers_history)*100:.1f}%\n"
        )

    await update.message.reply_text(stats_text, parse_mode="HTML")


async def ticket_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /ticket"""
    keyboard = [
        [InlineKeyboardButton(f"Билет {i}", callback_data=f"ticket_{i}")]
        for i in range(1, 41)  # 40 билетов
    ]

    # Группируем кнопки по 5 в ряд для лучшего отображения
    grouped_keyboard = [keyboard[i : i + 5] for i in range(0, len(keyboard), 5)]
    grouped_keyboard.append(
        [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
    )

    await update.message.reply_text(
        "Выберите билет:", reply_markup=InlineKeyboardMarkup(grouped_keyboard)
    )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    print(f"Ошибка: {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "Произошла ошибка. Пожалуйста, попробуйте еще раз или /start"
        )


def main():
    """Основная функция запуска бота"""
    if not tickets_data:
        print("Ошибка: Не удалось загрузить данные билетов!")
        return

    print(f"Загружено {len(tickets_data)} билетов")

    application = Application.builder().token(TOKEN).build()

    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("exam", exam_command))
    application.add_handler(CommandHandler("express", express_command))
    application.add_handler(CommandHandler("marathon", marathon_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("ticket", ticket_command))

    # Обработчики callback-запросов
    application.add_handler(CallbackQueryHandler(set_mode, pattern=r"^mode_"))
    application.add_handler(CallbackQueryHandler(handle_answer, pattern=r"^answer_"))
    application.add_handler(
        CallbackQueryHandler(handle_skip_question, pattern=r"^skip_question")
    )
    application.add_handler(CallbackQueryHandler(main_menu, pattern=r"^main_menu$"))
    application.add_handler(CallbackQueryHandler(select_mode, pattern=r"^select_mode$"))
    application.add_handler(CallbackQueryHandler(cancel_exam, pattern=r"^cancel_exam$"))
    application.add_handler(
        CallbackQueryHandler(select_ticket, pattern=r"^select_ticket$")
    )
    application.add_handler(CallbackQueryHandler(set_ticket, pattern=r"^ticket_\d+$"))

    application.add_error_handler(error_handler)

    print("Бот запущен...")
    application.run_polling()


if __name__ == "__main__":
    main()
