# The fake "bank" — a standalone, controllable processor (slow / fail / dedupe).
FROM python:3.11-slim

RUN useradd --create-home appuser
WORKDIR /srv

# Deps first (cached), then the mock's source.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

USER appuser
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000"]
