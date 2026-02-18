from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup

try:
    from .config import Settings
    from .storage import InMemoryStorage
except ImportError:
    from config import Settings
    from storage import InMemoryStorage


class AdminStates(StatesGroup):
    waiting_broadcast = State()



def admin_router(settings: Settings, storage: InMemoryStorage) -> Router:
    router = Router(name='admin')

    def is_admin(user_id: int) -> bool:
        return user_id in settings.admin_ids

    @router.message(Command('admin'))
    async def admin_entry(message: Message) -> None:
        if not is_admin(message.from_user.id):
            await message.answer('Доступ запрещен.')
            return

        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text='/stats')],
                [KeyboardButton(text='/broadcast')],
            ],
            resize_keyboard=True,
        )
        await message.answer('Панель администратора активна.', reply_markup=keyboard)

    @router.message(Command('stats'))
    async def show_stats(message: Message) -> None:
        if not is_admin(message.from_user.id):
            await message.answer('Доступ запрещен.')
            return

        stats = storage.stats()
        text = (
            '📊 Статистика\n'
            f'• Всего пользователей: {stats["total_users"]}\n'
            f'• Активных диалогов: {stats["active_dialogs"]}\n'
            f'• Сообщений за сутки: {stats["messages_24h"]}\n'
            f'• Новых запусков: {stats["starts_24h"]}'
        )
        await message.answer(text)

    @router.message(Command('broadcast'))
    async def broadcast_start(message: Message, state: FSMContext) -> None:
        if not is_admin(message.from_user.id):
            await message.answer('Доступ запрещен.')
            return

        await state.set_state(AdminStates.waiting_broadcast)
        await message.answer('Отправьте текст рассылки одним сообщением.')

    @router.message(AdminStates.waiting_broadcast, F.text)
    async def broadcast_send(message: Message, state: FSMContext) -> None:
        if not is_admin(message.from_user.id):
            await message.answer('Доступ запрещен.')
            await state.clear()
            return

        delivered = 0
        failed = 0
        for user_id in storage.all_user_ids():
            try:
                await message.bot.send_message(user_id, message.text)
                delivered += 1
            except Exception:
                failed += 1

        await state.clear()
        await message.answer(f'Рассылка завершена. Доставлено: {delivered}, ошибок: {failed}.')

    return router
