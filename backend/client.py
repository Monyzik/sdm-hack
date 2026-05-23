import openai
import os
from dotenv import load_dotenv


load_dotenv()

YANDEX_CLOUD_FOLDER = os.getenv("YANDEX_CLOUD_FOLDER")
YANDEX_CLOUD_API_KEY = os.getenv("YANDEX_CLOUD_API_KEY")
YANDEX_CLOUD_MODEL = os.getenv("YANDEX_CLOUD_MODEL")


client = openai.OpenAI(
    api_key=YANDEX_CLOUD_API_KEY,
    base_url="https://ai.api.cloud.yandex.net/v1",
    project=YANDEX_CLOUD_FOLDER
)
