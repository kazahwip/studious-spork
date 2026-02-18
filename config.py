from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Set

from dotenv import load_dotenv


@dataclass(slots=True)
class Settings:
    bot_token: str
    nscale_service_token: str
    nscale_model: str
    nscale_base_url: str
    nscale_max_tokens: int
    proxy_url: str
    admin_ids: Set[int]
    log_channel_id: int
    request_timeout: int
    rate_limit_messages: int
    rate_limit_period: int



def _parse_admin_ids(raw_value: str | None) -> Set[int]:
    if not raw_value:
        return set()
    result: Set[int] = set()
    for item in raw_value.split(','):
        item = item.strip()
        if not item:
            continue
        result.add(int(item))
    return result



def load_settings() -> Settings:
    load_dotenv()

    bot_token = os.getenv('BOT_TOKEN', '').strip()
    nscale_service_token = os.getenv('NSCALE_SERVICE_TOKEN', '').strip()

    if not bot_token:
        raise RuntimeError('BOT_TOKEN is not set')
    if not nscale_service_token:
        raise RuntimeError('NSCALE_SERVICE_TOKEN is not set')

    return Settings(
        bot_token=bot_token,
        nscale_service_token=nscale_service_token,
        nscale_model=os.getenv('NSCALE_MODEL', 'meta-llama/Llama-3.1-8B-Instruct').strip(),
        nscale_base_url=os.getenv('NSCALE_BASE_URL', 'https://inference.api.nscale.com/v1').strip(),
        nscale_max_tokens=int(os.getenv('NSCALE_MAX_TOKENS', '800')),
        proxy_url=os.getenv('PROXY_URL', '').strip(),
        admin_ids=_parse_admin_ids(os.getenv('ADMIN_IDS')),
        log_channel_id=int(os.getenv('LOG_CHANNEL_ID', '0')),
        request_timeout=int(os.getenv('REQUEST_TIMEOUT', '60')),
        rate_limit_messages=int(os.getenv('RATE_LIMIT_MESSAGES', '6')),
        rate_limit_period=int(os.getenv('RATE_LIMIT_PERIOD', '10')),
    )
