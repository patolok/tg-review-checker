FROM python:3.11-slim

# Отключение буферизации логов
ENV PYTHONUNBUFFERED=1

# Устанавка зависимостей для ChromeDriver
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    fonts-liberation \
    libnss3 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libxshmfence1 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Конфигурация путей к СhromeDriver
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_BIN=/usr/bin/chromedriver

WORKDIR /app

COPY requirements.txt checker_tg.py config.txt .
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "checker_tg.py"]

