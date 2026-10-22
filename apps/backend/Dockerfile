# Standard library only, so there is no install step. ffmpeg transcodes Telegram voice notes.
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

# stark.db is written next to the code, so the app user owns the directory.
RUN useradd --create-home stark && chown -R stark /app
USER stark

ENV HOST=0.0.0.0 PORT=8000 PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python", "server.py"]
