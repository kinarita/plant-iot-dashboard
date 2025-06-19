from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, SensorData
import dht11
import sen0193
import RPi.GPIO as GPIO
from datetime import datetime
import logging
import os
import time
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv

# --- .env読み込み ---
load_dotenv()
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASS = os.getenv("GMAIL_PASS")
TO_EMAIL = os.getenv("TO_EMAIL")

# --- センサーロケーション設定 ---
SENSOR_LOCATION = "ohana_001"  # ← この行を追加

# --- ログ設定 ---
log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "sensor.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- メール送信共通関数 ---
def send_email(subject, body):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = TO_EMAIL
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(GMAIL_USER, GMAIL_PASS)
            server.send_message(msg)
            logger.info("📧 メール送信しました: " + subject)
    except Exception as e:
        logger.error(f"❌ メール送信に失敗しました: {e}")

# --- 水やりアラート通知 ---
def send_moisture_alert(soil_moisture, timestamp):
    subject = "💧水やりアラート（土壌湿度低下）"
    body = f"⚠️ 土壌湿度が {soil_moisture}% に低下しました。\n\n日時: {timestamp}\n\n水やりを検討してください。"
    send_email(subject, body)

# --- 異常通知（センサー失敗） ---
def send_sensor_error(sensor_name):
    subject = f"❌センサー読み取り失敗: {sensor_name}"
    body = f"{sensor_name} が最大リトライ回数を超えても読み取れませんでした。\nご確認ください。"
    send_email(subject, body)

# --- 異常通知（例外） ---
def send_exception_alert(error_message):
    subject = "❗センサーシステムで例外が発生しました"
    body = f"次のエラーが発生しました：\n\n{error_message}"
    send_email(subject, body)

# --- GPIO初期化 ---
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

# --- センサー初期化 ---
dht_sensor = dht11.DHT11(pin=14)
soil_sensor = sen0193.SEN0193(channel=0, vref=5.0)

# --- SQLite DB初期化 ---
from os.path import dirname, join
db_path = join(dirname(__file__), 'sensor_data.db')
engine = create_engine(f'sqlite:///{db_path}')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

# --- センサーデータ取得 ---
try:
    MAX_RETRIES = 3

    # --- DHT11 読み取り ---
    dht_valid = False
    for attempt in range(1, MAX_RETRIES + 1):
        result = dht_sensor.read()
        if result.is_valid():
            dht_valid = True
            temperature = result.temperature
            humidity = result.humidity
            break
        else:
            logger.warning(f"⚠ DHT11 読み取り失敗（{attempt}回目）")
            time.sleep(1)
    if not dht_valid:
        send_sensor_error("DHT11")

    # --- SEN0193 読み取り ---
    soil_valid = False
    for attempt in range(1, MAX_RETRIES + 1):
        if soil_sensor.is_valid():
            soil_valid = True
            soil_moisture = soil_sensor.read_moisture_percentage()
            break
        else:
            logger.warning(f"⚠ 土壌湿度センサー 読み取り失敗（{attempt}回目）")
            time.sleep(1)
    if not soil_valid:
        send_sensor_error("SEN0193")

    # --- 保存と通知処理 ---
    if dht_valid and soil_valid:
        timestamp = datetime.now()
        new_data = SensorData(
            timestamp=timestamp,
            temperature=temperature,
            humidity=humidity,
            soil_moisture=soil_moisture,
            sensor_location=SENSOR_LOCATION
        )
        session.add(new_data)
        session.commit()
        logger.info(f"[{timestamp}] Logged: Temp={temperature}C, Hum={humidity}%, Moisture={soil_moisture}%")

        if soil_moisture < 30.0:
            send_moisture_alert(soil_moisture, timestamp)
    else:
        logger.info("⚠ 有効なセンサーが揃っていないため、データは保存されませんでした")

except Exception as e:
    logger.error(f"❌ 実行中に例外が発生しました: {e}")
    send_exception_alert(str(e))

finally:
    session.close()
    GPIO.cleanup()
