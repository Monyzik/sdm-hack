FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY sdm /app/sdm
COPY data /app/data
COPY scripts /app/scripts

EXPOSE 8010

CMD ["uvicorn", "sdm.agents.api:app", "--host", "0.0.0.0", "--port", "8010"]
