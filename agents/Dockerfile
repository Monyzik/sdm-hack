FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY agents/requirements.txt /app/agents/requirements.txt
RUN pip install --no-cache-dir -r /app/agents/requirements.txt

COPY agents /app/agents

EXPOSE 8010

CMD ["uvicorn", "agents.app:app", "--host", "0.0.0.0", "--port", "8010"]
