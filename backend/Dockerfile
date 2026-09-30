FROM python:3.11-slim

RUN ln -snf /usr/share/zoneinfo/Asia/Ho_Chi_Minh /etc/localtime && echo Asia/Ho_Chi_Minh > /etc/timezone

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chmod +x /app/docker-entrypoint.sh

# Embedding inference runs outside the API container through the configured API.
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "src.main:app", "--workers", "1", "--timeout", "300", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
