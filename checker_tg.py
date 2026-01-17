import time
import sys
import re
import os
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException,
)


# ANSI цвета для консоли
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"
YELLOW = "\033[93m"


# --- ЧТЕНИЕ ИЗ КОНФИГА ---
def load_config(filename="config.txt"):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    config = {}

    if not os.path.exists(path):
        print(f"Файл {filename} не найден")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            config[key.strip()] = value.strip()

    return config


# --- ВАЛИДАЦИЯ ТОКЕНА ТГ-БОТА ---
def check_telegram_token():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
    try:
        resp = requests.get(url, timeout=10)
    except Exception as e:
        print(f"{RED}Ошибка соединения с Telegram API: {e}{RESET}")
        sys.exit(1)

    if resp.status_code != 200:
        print(f"{RED}Неверный Telegram BOT TOKEN! {RESET}")
        sys.exit(1)

    data = resp.json()
    if not data.get("ok"):
        print(f"{RED}Telegram BOT TOKEN не прошёл проверку!{RESET}")
        sys.exit(1)

    bot_name = data["result"].get("username", "unknown")
    print(f"{GREEN}\nИспользуется Telegram бот: @{bot_name} {RESET}")


# --- ЗАГРУЗКА НАСТРОЕК ---
config = load_config()
USERNAME, PASSWORD, BOT_TOKEN, USER_ID = (
    config.get(k) or sys.exit(f"В config.txt не задано: {k}")
    for k in ("USERNAME", "PASSWORD", "BOT_TOKEN", "USER_ID")
)
check_telegram_token()
CHECK_INTERVAL = int(config.get("CHECK_INTERVAL", 180))
PAGE_LOAD_WAIT = int(config.get("PAGE_LOAD_WAIT", 15))
START_URL = "https://platform.21-school.ru/"


# --- TELEGRAM ---
def send_telegram(message: str):
    if not BOT_TOKEN or not USER_ID:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": USER_ID, "text": message})
    except Exception as e:
        print(f"{RED}Ошибка при отправке в Telegram: {e}{RESET}")


# --- SELENIUM ---
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--blink-settings=imagesEnabled=false")
driver = webdriver.Chrome(options=chrome_options)


def login():
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        print(
            f"{GREEN}Авторизация на платформе (попытка {attempt} из {max_attempts}).{RESET}"
        )
        try:
            driver.get(START_URL)
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.NAME, "username"))
            )
            username_field = driver.find_element(By.NAME, "username")
            username_field.clear()
            username_field.send_keys(USERNAME)
            password_field = driver.find_element(By.NAME, "password")
            password_field.clear()
            password_field.send_keys(PASSWORD)

            login_button = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "button[type='submit'], input[type='submit']")
                )
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", login_button)
            time.sleep(1)
            login_button.click()

            time.sleep(20)

            if driver.current_url == START_URL:
                print(f"{GREEN}Авторизация на платформе удалась.{RESET}")
                return True
            else:
                print(
                    f"{YELLOW}Авторизация не удалась на попытке {attempt}. Пробуем снова...{RESET}"
                )

        except (TimeoutException, NoSuchElementException, WebDriverException):
            print(f"{RED}Авторизация не удалась на попытке {attempt}{RESET}")
            time.sleep(5)  # Пауза между попытками

        except KeyboardInterrupt:
            raise

    print(f"{RED}Авторизация не удалась после {max_attempts} попыток!{RESET}")
    return False


def get_events():
    """
    Возвращает множество строк событий из виджета 'Your agenda'.
    Формат строки: 'HH:MM–HH:MM | <Заголовок> — <Описание> [ (обязательность)]'
    """
    try:
        # Ждём сам виджет "Your agenda"
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "[data-testid='components.Agenda.WidgetAgenda']")
            )
        )
    except KeyboardInterrupt:
        raise
    except Exception:
        return None

    widget = driver.find_element(
        By.CSS_SELECTOR, "[data-testid='components.Agenda.WidgetAgenda']"
    )
    cards = widget.find_elements(By.CSS_SELECTOR, "[data-testid='eventItem.card']")

    events = set()

    for card in cards:
        # Время начала/конца
        t_start = card.find_element(
            By.CSS_SELECTOR, "[data-testid='eventItem.timeStart']"
        ).text.strip()
        t_end_e = card.find_elements(
            By.CSS_SELECTOR, "[data-testid='eventItem.timeEnd']"
        )
        t_end = t_end_e[0].text.strip() if t_end_e else ""

        # Заголовок/описание
        title_e = card.find_elements(By.CSS_SELECTOR, "[data-testid='eventItem.title']")
        title = title_e[0].text.strip() if title_e else ""

        desc_e = card.find_elements(
            By.CSS_SELECTOR, "[data-testid='eventItem.description']"
        )
        desc = desc_e[0].text.strip() if desc_e else ""

        # Обязательное мероприятие (бейдж)
        is_mandatory = bool(
            card.find_elements(
                By.CSS_SELECTOR, "[data-testid='components.MandatoryEventBadge']"
            )
        )

        # Сборка "ключа" события (стабильно и без склейки)
        time_part = f"{t_start}–{t_end}" if t_end else t_start

        # Для безымянных Event опираемся на описание; иначе — title — desc
        if title and title != "Event":
            label = f"{title} — {desc}".strip(" —")
        else:
            label = desc or title or "Event"

        if is_mandatory:
            label += " (обязательно)"

        # Нормализация пробелов
        label = re.sub(r"\s+", " ", label).strip()
        key = f"{time_part} | {label}"

        events.add(key)

    return events


# --- ОСНОВНОЙ ЦИКЛ ---
print("Скрипт сконфигурирован. Проверка каждые", CHECK_INTERVAL, "секунд.")

try:
    if not login():
        sys.exit(1)

    old_events = get_events()
    if old_events is None:
        print("Не удалось получить список событий при запуске.")
        sys.exit(1)

    print("\nТекущие события:")
    for ev in old_events:
        print(" •", ev)
    if old_events:
        send_telegram(
            "📋 Текущие события:\n" + "\n".join(f"• {ev}" for ev in old_events)
        )
    else:
        send_telegram("📋 На данный момент событий нет.")

    while True:
        now = datetime.now().strftime("%H:%M")
        print(f"\n[{now}] 🔎 Проверка")
        driver.refresh()
        time.sleep(PAGE_LOAD_WAIT)

        new_events = get_events()

        if new_events is None:
            print("Похоже, сессия разлогинилась. Авторизация заново...")
            if not login():
                time.sleep(CHECK_INTERVAL)
                continue
            new_events = get_events() or set()

        added = new_events - old_events
        removed = old_events - new_events

        if added:
            for ev in added:
                msg = f"[НОВОЕ СОБЫТИЕ] {ev}"
                print(f"{GREEN}{msg}{RESET}")
                send_telegram(msg)

        if removed:
            for ev in removed:
                msg = f"[СОБЫТИЕ УДАЛЕНО] {ev}"
                print(f"{RED}{msg}{RESET}")
                send_telegram(msg)

        if not added and not removed:
            print("Изменений не обнаружено.")

        old_events = new_events
        time.sleep(CHECK_INTERVAL)

except KeyboardInterrupt:
    print(f"\n{GREEN}⏹ Завершение работы по Ctrl+C...{RESET}")
    send_telegram("⏹ Скрипт остановлен вручную.")

except Exception as e:
    print(f"{RED}❌ Критическая ошибка: {e}{RESET}")
    send_telegram("❌ Скрипт упал")
    raise

finally:
    print("Закрываю браузер...")
    try:
        driver.quit()
    except Exception as e:
        print(f"Ошибка при закрытии браузера: {e}")
