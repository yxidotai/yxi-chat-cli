FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY tasks/test_ui/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements.txt

COPY tasks /app/tasks

ENV PYTHONPATH=/app

EXPOSE 8040
CMD ["uvicorn", "tasks.test_ui.mcp_service:app", "--host", "0.0.0.0", "--port", "8040"]
