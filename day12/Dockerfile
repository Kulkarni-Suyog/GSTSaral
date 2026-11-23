FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    USE_OFFLINE_EMBED=1 \
    PORT=7860

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY app ./app
COPY ui ./ui
COPY data ./data
COPY start.sh ./start.sh
RUN chmod +x /app/start.sh

EXPOSE 7860 8000 8501

CMD ["/app/start.sh"]
