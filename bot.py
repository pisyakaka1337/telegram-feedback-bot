import asyncio
import os
import json
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))  # задаётся через переменную окружения ADMIN_ID

MAP_FILE = "message_map.json"


def load_map() -> dict:
    if os.path.exists(MAP_FILE):
        with open(MAP_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_map(data: dict):
    with open(MAP_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


message_map: dict[str, int] = load_map()
known_users: set[int] = set()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


def user_display(user: types.User) -> str:
    name = user.full_name or "Без имени"
    username = f" (@{user.username})" if user.username else ""
    return f"{name}{username} [ID: {user.id}]"


@dp.message(CommandStart())
async def cmd_start(message: Message):
    known_users.add(message.from_user.id)
    await message.answer(
        "Привет! Отправь сюда своё сообщение, и я передам его владельцу."
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer(
            "Вы — администратор.\n\n"
            "Чтобы ответить пользователю:\n"
            "1. Найдите пересланное сообщение от нужного пользователя\n"
            "2. Нажмите «Ответить» (Reply) на это сообщение\n"
            "3. Напишите ваш ответ — он автоматически улетит пользователю"
        )
    else:
        await message.answer(
            "Просто напишите ваше сообщение — я передам его владельцу."
        )


@dp.message(F.from_user.id == ADMIN_ID)
async def handle_admin_message(message: Message):
    if not message.reply_to_message:
        await message.answer(
            "ℹ️ Чтобы ответить пользователю, используйте «Ответить» (Reply) "
            "на пересланное от него сообщение."
        )
        return

    replied_msg_id = str(message.reply_to_message.message_id)
    user_id = message_map.get(replied_msg_id)

    if not user_id:
        await message.answer(
            "❌ Не удалось найти пользователя для этого сообщения.\n"
            "Возможно, бот был перезапущен и потерял привязку."
        )
        return

    try:
        await bot.copy_message(
            chat_id=user_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id
        )
        await message.react([types.ReactionTypeEmoji(emoji="👍")])
    except Exception as e:
        logger.error(f"Ошибка при отправке ответа пользователю {user_id}: {e}")
        await message.answer(f"❌ Не удалось доставить ответ пользователю. Ошибка: {e}")


@dp.message()
async def handle_user_message(message: Message):
    user = message.from_user

    if user.id not in known_users:
        known_users.add(user.id)
        await message.answer(
            "Привет! Отправь сюда своё сообщение, и я передам его владельцу."
        )

    header = (
        f"📩 <b>Новое сообщение</b>\n"
        f"👤 {user_display(user)}"
    )

    try:
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=header,
            parse_mode="HTML"
        )

        forwarded = await bot.forward_message(
            chat_id=ADMIN_ID,
            from_chat_id=message.chat.id,
            message_id=message.message_id
        )

        message_map[str(forwarded.message_id)] = user.id
        save_map(message_map)

        await message.answer("✅ Сообщение передано! Ожидайте ответа.")

    except Exception as e:
        logger.error(f"Ошибка при пересылке сообщения от {user.id}: {e}")
        await message.answer(
            "⚠️ Произошла ошибка при отправке. Попробуйте ещё раз."
        )


async def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не задан! Укажите его в переменных окружения.")
    if ADMIN_ID == 000000000:
        raise ValueError("ADMIN_ID не задан! Укажите ваш Telegram ID в bot.py.")

    logger.info("Бот запускается...")
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
