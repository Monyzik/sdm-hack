import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field


load_dotenv()

DEFAULT_MODEL = os.getenv("AI_MODEL") or "gpt-5.4-mini"


class ProjectAnalysisResult(BaseModel):
    reasoning: str = Field(description="Краткое обоснование вывода")
    project_goal: str = Field(description="Основная цель проекта")
    budget: str = Field(description="Бюджет текущего проекта")
    confidence: int = Field(ge=0, le=100, description="Уверенность 0-100")


def get_response_format() -> dict[str, Any]:
    schema = ProjectAnalysisResult.model_json_schema()
    schema["additionalProperties"] = False

    return {
        "type": "json_schema",
        "json_schema": {
            "name": "project_analysis_result",
            "strict": True,
            "schema": schema,
        },
    }


def build_client() -> OpenAI:
    api_key = os.getenv("AI_TOKEN") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Не задан AI_TOKEN или OPENAI_API_KEY")

    return OpenAI(
        api_key=api_key,
        base_url=os.getenv("AI_URL") or None,
    )


SYSTEM_PROMPT = """
You are an AI agent for project documentation analysis.

Your task:
1. Analyze the provided project document.
2. Extract the main project goal.
3. Extract the budget of the current project.
4. Provide a short reasoning.
5. Return the result strictly according to the JSON schema.

Rules:
- Always respond in Russian.
- Return only valid JSON.
- Do not use markdown.
- Do not invent information.
- If information is missing, return "не найдено".
- Do not confuse the current project budget with budgets of old pilots or related initiatives.
- Extract the budget as accurately as possible.
- Keep the project goal concise and meaningful.
- confidence must reflect extraction certainty from 0 to 100.
"""


def call_llm(client: OpenAI, messages: list[dict[str, str]], model: str) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0,
        response_format=get_response_format(),
    )

    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("Модель вернула пустой ответ")

    return content


def query(
    document: str,
    max_attempts: int = 3,
    client: OpenAI | None = None,
    model: str = DEFAULT_MODEL,
) -> ProjectAnalysisResult:
    if max_attempts < 1:
        raise ValueError("max_attempts должен быть больше 0")

    llm_client = client or build_client()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": document},
    ]

    last_error: Exception | None = None
    last_content: str | None = None

    for _ in range(max_attempts):
        try:
            last_content = None
            last_content = call_llm(llm_client, messages, model)
            return ProjectAnalysisResult.model_validate_json(last_content)

        except Exception as e:
            last_error = e

            if last_content is not None:
                messages.append({
                    "role": "assistant",
                    "content": last_content,
                })

            messages.append({
                "role": "user",
                "content": (
                    "Previous response failed validation.\n\n"
                    f"Error:\n{e}\n\n"
                    "Return again only valid JSON according to the schema."
                ),
            })

    raise RuntimeError(
        f"Не удалось получить валидный JSON после {max_attempts} попыток"
    ) from last_error


def main() -> None:
    document = """ПРОЕКТНАЯ ЗАПИСКА № БК-42/17

Дата подготовки: 14.05.2026
Подразделение: Департамент цифровой трансформации
Куратор: Управление операционной эффективности

1. Общий контекст

В рамках стратегической инициативы банка на 2026–2027 годы рассматривается несколько направлений развития внутренних цифровых сервисов. Среди них: оптимизация процессов согласования договоров, обновление клиентских анкет, развитие BI-витрин для продуктовых команд, а также автоматизация контроля проектных портфелей.

По результатам совещания от 07.04.2026 было отмечено, что текущая нагрузка на руководителей проектов выросла на 31%, при этом количество параллельно сопровождаемых инициатив увеличилось с 8 до 15 на одного руководителя. Отдельно обсуждалась необходимость улучшения прозрачности проектных статусов, однако данная тема не является самостоятельной целью текущего проекта.

2. Предпосылки

В 2025 году банк уже запускал пилот по автоматической классификации задач в task tracker. Бюджет пилота составлял 3,2 млн ₽, но он был закрыт после завершения исследования применимости технологии. Также в архиве присутствует смежный проект по построению витрины проектных KPI с плановым бюджетом 6,8 млн ₽.

Текущий документ относится к новой инициативе и не должен смешиваться с указанными выше пилотами.

3. Описание инициативы

Проект направлен на создание цифрового помощника руководителя проекта, который будет автоматически анализировать данные из task tracker, проектных планов, бюджетных таблиц, реестров рисков и коммуникационных карт, выявлять отклонения по срокам, бюджету и ресурсам, а также формировать рекомендации по снижению рисков для руководителя проекта.

Ключевая цель проекта: разработать и внедрить AI-инструмент для автоматизации мониторинга состояния банковских проектов и поддержки руководителей проектов в принятии управленческих решений.

4. Ожидаемые эффекты

Ожидается снижение времени ручной подготовки проектной отчетности на 40–50%, повышение своевременности выявления рисков и уменьшение количества незамеченных отклонений по критическим инициативам.

Дополнительные эффекты:
- ускорение подготовки weekly status report;
- автоматическое выявление просроченных задач;
- обнаружение перерасхода бюджета;
- формирование кратких executive summary;
- снижение нагрузки на PMO.

5. Финансовые параметры

Предварительная оценка затрат на инфраструктуру составляет 1,4 млн ₽.
Оценка затрат на интеграции с внутренними системами — 2,1 млн ₽.
Резерв на доработки после пилота — 900 тыс. ₽.
Фонд оплаты внешней команды разработки — 5,6 млн ₽.
Внутренние трудозатраты сотрудников банка учитываются отдельно и не входят в бюджет проекта.

Итоговый утвержденный бюджет текущего проекта составляет 10 млн ₽, включая разработку, интеграции, тестирование, инфраструктуру и пилотное внедрение.

6. Ограничения

Проект не предполагает замену существующей системы управления проектами. Инструмент должен работать как аналитический слой поверх существующих источников данных.

7. Риски

Основные риски:
- неполнота исторических данных;
- различия в форматах ведения проектов;
- ограничение доступа к бюджетной информации;
- сопротивление пользователей;
- необходимость согласования с ИБ.

8. Коммуникации

Еженедельные статусы предоставляются в PMO по пятницам до 16:00.
Демо для бизнес-заказчиков запланировано на 28.06.2026.
Отдельный бюджет на коммуникационную кампанию не выделяется.

9. Примечание

Все суммы в документе указаны справочно, кроме утвержденного бюджета текущего проекта в разделе 5."""
    result = query(document)

    print(result.model_dump_json(indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
