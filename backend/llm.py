import openai
import os
from dotenv import load_dotenv
from docx import Document
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from datetime import datetime
import json


load_dotenv()

YANDEX_CLOUD_FOLDER = os.getenv("YANDEX_CLOUD_FOLDER")
YANDEX_CLOUD_API_KEY = os.getenv("YANDEX_CLOUD_API_KEY")
YANDEX_CLOUD_MODEL = os.getenv("YANDEX_CLOUD_MODEL")


client = openai.OpenAI(
  api_key=YANDEX_CLOUD_API_KEY,
  base_url="https://ai.api.cloud.yandex.net/v1",
  project=YANDEX_CLOUD_FOLDER
)

response = client.responses.create(
  model=f"gpt://{YANDEX_CLOUD_FOLDER}/{YANDEX_CLOUD_MODEL}",
  temperature=0.3,
  instructions="",
  input="Как ты относишься к банкам",
  max_output_tokens=500
)


print(response.output_text)