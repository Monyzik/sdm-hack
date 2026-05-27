FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY agents/requirements.txt /app/agents/requirements.txt
RUN pip install --no-cache-dir -r /app/agents/requirements.txt

COPY agents /app/agents
COPY backend /app/backend
COPY scripts /app/scripts
COPY data /app/data

EXPOSE 8010

CMD ["uvicorn", "sdm.agents.api:app", "--host", "0.0.0.0", "--port", "8010"]
