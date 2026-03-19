import os
from dotenv import load_dotenv
import requests

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_test_message():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Missing TELEGRAM configs")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": "🤖 [바이낸스 봇] 텔레그램 연동이 성공적으로 완료되었습니다! 이제부터 자동 매매 내역이 이곳으로 전송됩니다."}
    try:
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code == 200:
            print("텔레그램 테스트 메시지 전송 성공!")
        else:
            print(f"텔레그램 전송 실패: {response.text}")
    except Exception as e:
        print(f"❌ Telegram Notification Failed: {e}")

if __name__ == "__main__":
    send_test_message()
