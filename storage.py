from __future__ import annotations

import json
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Deque, Dict, List, Optional


UTC = timezone.utc


@dataclass(slots=True)
class SessionData:
    session_id: str
    user_id: int
    history: List[dict[str, str]] = field(default_factory=list)
    messages_count: int = 0
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class InMemoryStorage:
    def __init__(self, state_file: str = 'bot_state.json') -> None:
        self._users: set[int] = set()
        self._sessions: Dict[int, SessionData] = {}
        self._message_events: Deque[datetime] = deque()
        self._start_events: Deque[datetime] = deque()
        self._rate_limit_events: Dict[int, Deque[datetime]] = defaultdict(deque)
        self._state_path = Path(state_file)
        self._load_state()

    def register_user(self, user_id: int) -> None:
        self._users.add(user_id)
        self._save_state()

    def all_user_ids(self) -> list[int]:
        return list(self._users)

    def track_start(self) -> None:
        self._start_events.append(datetime.now(UTC))
        self._trim_old(self._start_events, timedelta(hours=24))
        self._save_state()

    def set_session(self, user_id: int, session: SessionData) -> None:
        self._sessions[user_id] = session

    def get_session(self, user_id: int) -> Optional[SessionData]:
        return self._sessions.get(user_id)

    def clear_session(self, user_id: int) -> Optional[SessionData]:
        return self._sessions.pop(user_id, None)

    def increment_messages(self, user_id: int) -> None:
        session = self._sessions.get(user_id)
        if not session:
            return
        session.messages_count += 1
        self._message_events.append(datetime.now(UTC))
        self._trim_old(self._message_events, timedelta(hours=24))
        self._save_state()

    def is_rate_limited(self, user_id: int, limit: int, period_seconds: int) -> bool:
        now = datetime.now(UTC)
        bucket = self._rate_limit_events[user_id]
        period = timedelta(seconds=period_seconds)

        while bucket and now - bucket[0] > period:
            bucket.popleft()

        if len(bucket) >= limit:
            return True

        bucket.append(now)
        return False

    def stats(self) -> dict[str, int]:
        self._trim_old(self._message_events, timedelta(hours=24))
        self._trim_old(self._start_events, timedelta(hours=24))

        active_dialogs = sum(1 for session in self._sessions.values() if session.active)
        return {
            'total_users': len(self._users),
            'active_dialogs': active_dialogs,
            'messages_24h': len(self._message_events),
            'starts_24h': len(self._start_events),
        }

    @staticmethod
    def _trim_old(bucket: Deque[datetime], ttl: timedelta) -> None:
        now = datetime.now(UTC)
        while bucket and now - bucket[0] > ttl:
            bucket.popleft()

    def _load_state(self) -> None:
        if not self._state_path.exists():
            return
        try:
            raw = json.loads(self._state_path.read_text(encoding='utf-8'))
            users = raw.get('users', [])
            messages = raw.get('message_events', [])
            starts = raw.get('start_events', [])

            self._users = {int(u) for u in users}
            self._message_events = deque(self._parse_dt(x) for x in messages if self._parse_dt(x) is not None)
            self._start_events = deque(self._parse_dt(x) for x in starts if self._parse_dt(x) is not None)
        except Exception:
            # Если файл поврежден, начинаем с чистого состояния.
            self._users = set()
            self._message_events = deque()
            self._start_events = deque()

    def _save_state(self) -> None:
        try:
            payload = {
                'users': sorted(self._users),
                'message_events': [x.isoformat() for x in self._message_events],
                'start_events': [x.isoformat() for x in self._start_events],
            }
            self._state_path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        except Exception:
            pass

    @staticmethod
    def _parse_dt(value: str) -> datetime | None:
        try:
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        except Exception:
            return None
