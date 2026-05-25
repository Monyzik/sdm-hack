from __future__ import annotations

import os
from functools import lru_cache

import openai
from dotenv import load_dotenv

load_dotenv()

YANDEX_CLOUD_FOLDER = os.getenv("YANDEX_CLOUD_FOLDER")
YANDEX_CLOUD_API_KEY = os.getenv("YANDEX_CLOUD_API_KEY")
YANDEX_CLOUD_MODEL = os.getenv("YANDEX_CLOUD_MODEL")


def get_yandex_model_uri() -> str:
    if not YANDEX_CLOUD_MODEL:
        raise ValueError("Не задан YANDEX_CLOUD_MODEL в окружении.")
    if YANDEX_CLOUD_MODEL.startswith("gpt://"):
        return YANDEX_CLOUD_MODEL
    if not YANDEX_CLOUD_FOLDER:
        raise ValueError("Не задан YANDEX_CLOUD_FOLDER в окружении.")
    return f"gpt://{YANDEX_CLOUD_FOLDER}/{YANDEX_CLOUD_MODEL}"


@lru_cache(maxsize=1)
def get_yandex_client() -> openai.OpenAI:
    if not YANDEX_CLOUD_API_KEY:
        raise ValueError("Не задан YANDEX_CLOUD_API_KEY в окружении.")

    return openai.OpenAI(
        api_key=YANDEX_CLOUD_API_KEY,
        base_url="https://ai.api.cloud.yandex.net/v1",
        project=YANDEX_CLOUD_FOLDER,
    )
