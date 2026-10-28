FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements-jobs.txt .
RUN pip install --no-cache-dir -r requirements-jobs.txt

COPY src ./src
COPY configs ./configs

# Data, state and logs live in mounted volumes, never in the image.
# Secrets come from --env-file at run time, never from the image.
CMD ["python", "-m", "src.data.update"]