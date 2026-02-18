from __future__ import annotations

import asyncio
import random
import uuid
from time import monotonic

from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup

try:
    from .config import Settings
    from .llm import LLMAPIError, NScaleClient
    from .logger import ChannelLogger
    from .storage import InMemoryStorage, SessionData
except ImportError:
    from config import Settings
    from llm import LLMAPIError, NScaleClient
    from logger import ChannelLogger
    from storage import InMemoryStorage, SessionData


class ChatState(StatesGroup):
    in_dialog = State()


BTN_START = '🔥 Начать чат'
BTN_ABOUT = 'ℹ️ О боте'
BTN_SUPPORT = '🆘 Поддержка'
BTN_NEXT = '➡️ Следующий собеседник'
BTN_END = '❌ Завершить диалог'


WELCOME_TEXT = (
    '✨ <b>Анонимный чат</b>\n\n'
    'Нажми <b>🔥 Начать чат</b>, и я найду собеседника за пару секунд 😉\n\n'
    '<i>Приватно, легко и без регистрации.</i>'
)

ABOUT_TEXT = (
    'ℹ️ <b>О боте</b>\n\n'
    'Это анонимный чат, где можно свободно общаться и знакомиться в легкой атмосфере 💬\n\n'
    '• без регистрации\n'
    '• быстрый старт\n'
    '• приватный формат общения'
)

SUPPORT_TEXT = (
    '🆘 <b>Поддержка</b>\n\n'
    'Есть вопрос, баг или идея по улучшению?\n'
    'Напиши в Telegram: <a href="https://t.me/socialbleed">@socialbleed</a>\n\n'
    'Мы на связи и поможем 🤝'
)

SEARCHING_TEXT = (
    '🔎 <b>Ищу собеседника...</b>\n'
)

DIALOG_FOUND_TEXT = (
    '💘 <b>Собеседник найден</b>\n'
    'Он уже онлайн 🔥\n\n'
    'Напиши первым сообщением и начнем 😉'
)

FALLBACK_TEXT = (
    '👋 Нажми <b>🔥 Начать чат</b>, и я подберу тебе собеседника\n'
    'прямо сейчас 💬'
)


def search_delay_seconds() -> float:
    return random.uniform(3.0, 6.0)


def typing_duration_seconds(reply_text: str) -> float:
    text_len = len((reply_text or '').strip())
    delay = 0.9 + (text_len * 0.035)
    return max(1.0, min(delay, 14.0))


async def send_typing_for(message: Message, seconds: float) -> None:
    end = monotonic() + seconds
    while True:
        left = end - monotonic()
        if left <= 0:
            return
        try:
            await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
        except Exception:
            return
        await asyncio.sleep(min(4.0, left))



def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_START)],
            [KeyboardButton(text=BTN_ABOUT), KeyboardButton(text=BTN_SUPPORT)],
        ],
        resize_keyboard=True,
    )



def chat_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_NEXT), KeyboardButton(text=BTN_END)],
        ],
        resize_keyboard=True,
    )



def user_router(
    settings: Settings,
    storage: InMemoryStorage,
    llm: NScaleClient,
    channel_logger: ChannelLogger,
) -> Router:
    router = Router(name='user')

    async def start_dialog(message: Message, state: FSMContext) -> None:
        session = storage.get_session(message.from_user.id)
        if session:
            session.active = False
            await channel_logger.dialog_finished(
                message.from_user.id,
                session.session_id,
                session.messages_count,
            )

        new_session = SessionData(session_id=str(uuid.uuid4()), user_id=message.from_user.id)
        storage.set_session(message.from_user.id, new_session)
        await state.set_state(ChatState.in_dialog)

        await channel_logger.dialog_started(message.from_user.id, new_session.session_id)
        await message.answer(SEARCHING_TEXT)
        await asyncio.sleep(search_delay_seconds())
        await message.answer(DIALOG_FOUND_TEXT, reply_markup=chat_keyboard())

    @router.message(CommandStart())
    async def command_start(message: Message, state: FSMContext) -> None:
        user = message.from_user
        storage.register_user(user.id)
        storage.track_start()
        await state.clear()

        await channel_logger.startup(user.id, user.username)
        await message.answer(WELCOME_TEXT, reply_markup=main_menu_keyboard())

    @router.message(F.text == BTN_START)
    async def menu_start_dialog(message: Message, state: FSMContext) -> None:
        storage.register_user(message.from_user.id)
        await start_dialog(message, state)

    @router.message(F.text == BTN_ABOUT)
    async def about(message: Message) -> None:
        await message.answer(ABOUT_TEXT)

    @router.message(F.text == BTN_SUPPORT)
    async def support(message: Message) -> None:
        await message.answer(SUPPORT_TEXT, disable_web_page_preview=True)

    @router.message(F.text == BTN_END)
    async def end_dialog(message: Message, state: FSMContext) -> None:
        session = storage.clear_session(message.from_user.id)
        await state.clear()

        if session:
            session.active = False
            await channel_logger.dialog_finished(
                message.from_user.id,
                session.session_id,
                session.messages_count,
            )

        await message.answer('❌ <b>Диалог завершен</b>\n\nВозвращаю тебя в меню ✨', reply_markup=main_menu_keyboard())

    @router.message(F.text == BTN_NEXT)
    async def next_dialog(message: Message, state: FSMContext) -> None:
        old_session = storage.clear_session(message.from_user.id)
        if old_session:
            old_session.active = False
            await channel_logger.dialog_finished(
                message.from_user.id,
                old_session.session_id,
                old_session.messages_count,
            )

        await start_dialog(message, state)

    @router.message(ChatState.in_dialog, F.text)
    async def chat_message(message: Message, state: FSMContext) -> None:
        user_id = message.from_user.id

        if storage.is_rate_limited(
            user_id,
            limit=settings.rate_limit_messages,
            period_seconds=settings.rate_limit_period,
        ):
            await message.answer('⏳ Слишком быстро 😉 Подожди пару секунд и продолжим.')
            return

        session = storage.get_session(user_id)
        if not session:
            await state.clear()
            await message.answer('Сессия завершена. Нажми <b>🔥 Начать чат</b>, чтобы открыть новую.')
            return

        session.history.append({'role': 'user', 'content': message.text})

        try:
            reply = await llm.generate_reply(session.history)
        except LLMAPIError as exc:
            await channel_logger.api_error(user_id, str(exc))
            if str(exc) == 'NSCALE_RATE_LIMIT':
                await message.answer('⚠️ Сервис временно перегружен. Попробуй еще раз через минуту.')
                return
            if str(exc) == 'NSCALE_MODEL_NOT_FOUND':
                await message.answer('⚙️ Модель сейчас недоступна. Проверь NSCALE_MODEL в .env.')
                return
            if str(exc) == 'NSCALE_AUTH_ERROR':
                await message.answer('🔑 Проблема с ключом NSCALE. Проверь NSCALE_SERVICE_TOKEN в .env.')
                return
            if str(exc) == 'NSCALE_TIMEOUT':
                await message.answer('⌛ NSCALE отвечает слишком долго. Попробуй еще раз через пару секунд.')
                return
            if str(exc) == 'PROXY_SOCKS_NOT_SUPPORTED_INSTALL_AIOHTTP_SOCKS':
                await message.answer('🧩 Нужен пакет aiohttp-socks для SOCKS5. Установи зависимости и перезапусти бота.')
                return
            await message.answer('💤 Собеседник немного занят. Давай попробуем еще раз через пару секунд.')
            return

        await send_typing_for(message, typing_duration_seconds(reply))

        session.history.append({'role': 'assistant', 'content': reply})
        storage.increment_messages(user_id)

        if len(session.history) > 30:
            session.history = session.history[-30:]

        await message.answer(reply)

    @router.message()
    async def fallback(message: Message) -> None:
        await message.answer(FALLBACK_TEXT, reply_markup=main_menu_keyboard())

    return router
