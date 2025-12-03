FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY tasks/word_table_export/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements.txt

COPY tasks /app/tasks

ENV PYTHONPATH=/app

EXPOSE 8000
CMD ["uvicorn", "tasks.word_table_export.mcp_service:app", "--host", "0.0.0.0", "--port", "8000"]
