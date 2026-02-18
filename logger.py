from __future__ import annotations

import logging
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest


logger = logging.getLogger(__name__)
UTC = timezone.utc


class ChannelLogger:
    def __init__(self, bot: Bot, channel_id: int) -> None:
        self.bot = bot
        self.channel_id = channel_id

    async def startup(self, user_id: int, username: str | None) -> None:
        text = (
            '🟢 Новый запуск\n'
            f'👤 ID: {user_id}\n'
            f'🪪 Username: @{username if username else "—"}\n'
            f'📅 Время: {self._now()}'
        )
        await self._send(text)

    async def dialog_started(self, user_id: int, session_id: str) -> None:
        text = (
            '💬 Начат диалог\n'
            f'👤 ID: {user_id}\n'
            f'🆔 Сессия: {session_id}\n'
            f'📅 Время: {self._now()}'
        )
        await self._send(text)

    async def dialog_finished(self, user_id: int, session_id: str, messages_count: int) -> None:
        text = (
            '🔴 Диалог завершен\n'
            f'👤 ID: {user_id}\n'
            f'🆔 Сессия: {session_id}\n'
            f'🔥 Сообщений: {messages_count}\n'
            f'📅 Время: {self._now()}'
        )
        await self._send(text)

    async def api_error(self, user_id: int, error: str) -> None:
        text = (
            '⚠️ Ошибка API\n'
            f'👤 ID: {user_id}\n'
            f'❗ Детали: {error[:500]}\n'
            f'📅 Время: {self._now()}'
        )
        await self._send(text)

    async def _send(self, text: str) -> None:
        if not self.channel_id:
            return
        try:
            await self.bot.send_message(self.channel_id, text)
        except TelegramBadRequest as exc:
            logger.warning('Failed to send log to channel: %s', exc)

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')
