import os
import json
import time
import requests
import schedule
from datetime import datetime, timedelta
from anthropic import Anthropic

# ===================== SOZLAMALAR =====================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "@your_channel")
FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY", "YOUR_FOOTBALL_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "YOUR_ANTHROPIC_API_KEY")

# Joylangan yangiliklar ID larini saqlash (takrorlanmasligi uchun)
SENT_NEWS_FILE = "sent_news.json"

# ======================================================

client = Anthropic(api_key=ANTHROPIC_API_KEY)


def load_sent_news():
    """Avval yuborilgan yangiliklar ID larini yuklash"""
    if os.path.exists(SENT_NEWS_FILE):
        with open(SENT_NEWS_FILE, "r") as f:
            return json.load(f)
    return []


def save_sent_news(sent_ids):
    """Yuborilgan yangiliklar ID larini saqlash"""
    # Oxirgi 500 ta ID ni saqlash (xotira uchun)
    sent_ids = sent_ids[-500:]
    with open(SENT_NEWS_FILE, "w") as f:
        json.dump(sent_ids, f)


def get_football_news():
    """football-api.com dan so'nggi yangiliklar olish"""
    url = "https://v3.football.api-sports.io/fixtures"
    headers = {
        "x-apisports-key": FOOTBALL_API_KEY
    }
    
    today = datetime.now().strftime("%Y-%m-%d")
    params = {
        "date": today,
        "timezone": "Asia/Tashkent"
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("response", [])
    except requests.RequestException as e:
        print(f"❌ API xatosi: {e}")
        return []


def get_recent_results():
    """Kecha tugagan matchlar natijalarini olish"""
    url = "https://v3.football.api-sports.io/fixtures"
    headers = {
        "x-apisports-key": FOOTBALL_API_KEY
    }
    
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    params = {
        "date": yesterday,
        "status": "FT",  # Full Time - tugagan matchlar
        "timezone": "Asia/Tashkent"
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("response", [])
    except requests.RequestException as e:
        print(f"❌ API xatosi: {e}")
        return []


def create_post_with_claude(match_data, post_type="today"):
    """Claude yordamida chiroyli Telegram post yaratish"""
    
    if post_type == "today":
        prompt = f"""
Quyidagi bugungi futbol o'yinlari haqida Telegram kanalga chiroyli post yoz.
Post O'ZBEK TILIDA bo'lishi kerak.

Ma'lumotlar: {json.dumps(match_data, ensure_ascii=False, indent=2)}

Qoidalar:
1. Faqat taniqli ligalar (Premier League, La Liga, Champions League, Serie A, Bundesliga, UEL)
2. Emoji ko'p ishlatgin (⚽🔥💥🏆)
3. Qisqa va qiziqarli matn yoz
4. Match vaqtlarini O'zbekiston vaqtida ko'rsat
5. Maksimum 5 ta o'yin ko'rsat
6. Postni #futbol #bugun hashtaglari bilan tugat

Format:
⚽ BUGUNGI O'YINLAR
[Sana]

🔴 [Jamoa1] vs [Jamoa2]
🕐 [Vaqt] | 🏆 [Liga]

...
"""
    else:  # results
        prompt = f"""
Quyidagi kechagi futbol natijalari haqida Telegram kanalga chiroyli post yoz.
Post O'ZBEK TILIDA bo'lishi kerak.

Ma'lumotlar: {json.dumps(match_data, ensure_ascii=False, indent=2)}

Qoidalar:
1. Faqat tugagan o'yinlar natijasini yoz
2. Emoji ko'p ishlatgin (⚽🔥💥🏆🎯)
3. G'olib jamoani ajratib ko'rsat
4. Maksimum 5 ta natija ko'rsat
5. Eng ajoyib natijani birinchi qo'y
6. Postni #futbol #natijalar hashtaglari bilan tugat

Format:
📊 KECHAGI NATIJALAR
[Sana]

✅ [Jamoa1] [Hisob] [Jamoa2]
🏆 [Liga]

...
"""

    try:
        message = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return message.content[0].text
    except Exception as e:
        print(f"❌ Claude xatosi: {e}")
        return None


def send_to_telegram(text):
    """Telegram kanaliga post yuborish"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        print(f"✅ Post muvaffaqiyatli yuborildi: {datetime.now()}")
        return True
    except requests.RequestException as e:
        print(f"❌ Telegram xatosi: {e}")
        return False


def post_todays_matches():
    """Bugungi matchlarni post qilish"""
    print(f"\n🔄 Bugungi matchlar tekshirilmoqda... {datetime.now()}")
    
    matches = get_football_news()
    
    if not matches:
        print("ℹ️ Bugun match topilmadi")
        return
    
    # Faqat taniqli ligalar filteri
    top_leagues = [39, 140, 2, 3, 135, 78, 61]  # PL, La Liga, UCL, UEL, Serie A, Bundesliga, Ligue 1
    filtered = [m for m in matches if m.get("league", {}).get("id") in top_leagues]
    
    if not filtered:
        print("ℹ️ Taniqli ligalarda bugun match yo'q")
        return
    
    # Claude bilan post yaratish
    post_text = create_post_with_claude(filtered[:5], "today")
    
    if post_text:
        send_to_telegram(post_text)


def post_yesterdays_results():
    """Kechagi natijalarni post qilish"""
    print(f"\n🔄 Kechagi natijalar tekshirilmoqda... {datetime.now()}")
    
    results = get_recent_results()
    
    if not results:
        print("ℹ️ Kecha natija topilmadi")
        return
    
    top_leagues = [39, 140, 2, 3, 135, 78, 61]
    filtered = [m for m in results if m.get("league", {}).get("id") in top_leagues]
    
    if not filtered:
        print("ℹ️ Taniqli ligalarda kecha natija yo'q")
        return
    
    post_text = create_post_with_claude(filtered[:5], "results")
    
    if post_text:
        send_to_telegram(post_text)


def run_scheduler():
    """Scheduler ishga tushirish"""
    print("🚀 Football Bot ishga tushdi!")
    print(f"📢 Kanal: {TELEGRAM_CHANNEL_ID}")
    print("⏰ Har 30 daqiqada yangiliklar tekshiriladi\n")
    
    # Har 30 daqiqada bugungi matchlarni yuborish
    schedule.every(30).minutes.do(post_todays_matches)
    
    # Har kuni ertalab 8:00 da kechagi natijalarni yuborish
    schedule.every().day.at("08:00").do(post_yesterdays_results)
    
    # Birinchi marta darhol ishga tushirish
    post_todays_matches()
    
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    run_scheduler()
