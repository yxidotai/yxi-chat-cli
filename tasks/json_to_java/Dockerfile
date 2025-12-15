FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY tasks/json_to_java/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements.txt

COPY tasks /app/tasks

ENV PYTHONPATH=/app

EXPOSE 8030
CMD ["uvicorn", "tasks.json_to_java.mcp_service:app", "--host", "0.0.0.0", "--port", "8030"]
