import os
import json
import time
import requests
import schedule
from datetime import datetime, timedelta

# ===================== SOZLAMALAR =====================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "@your_channel")
FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY", "YOUR_FOOTBALL_API_KEY")

SENT_FIXTURES_FILE = "sent_fixtures.json"

TOP_LEAGUES = {
    2: "🏆 UEFA Champions League",
    3: "🥈 UEFA Europa League",
    39: "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League",
    140: "🇪🇸 La Liga",
    135: "🇮🇹 Serie A",
    78: "🇩🇪 Bundesliga",
    61: "🇫🇷 Ligue 1",
}

# ======================================================

def load_sent_fixtures():
    if os.path.exists(SENT_FIXTURES_FILE):
        with open(SENT_FIXTURES_FILE, "r") as f:
            return json.load(f)
    return []


def save_sent_fixtures(sent_ids):
    sent_ids = sent_ids[-500:]
    with open(SENT_FIXTURES_FILE, "w") as f:
        json.dump(sent_ids, f)


def get_fixtures(date_str, status=None):
    url = "https://v3.football.api-sports.io/fixtures"
    headers = {"x-apisports-key": FOOTBALL_API_KEY}
    params = {"date": date_str, "timezone": "Asia/Tashkent"}
    if status:
        params["status"] = status

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("response", [])
    except Exception as e:
        print(f"❌ API xatosi: {e}")
        return []


def format_time(utc_time_str):
    """UTC vaqtni O'zbekiston vaqtiga o'tkazish (+5)"""
    try:
        dt = datetime.fromisoformat(utc_time_str.replace("Z", "+00:00"))
        uz_time = dt + timedelta(hours=5)
        return uz_time.strftime("%H:%M")
    except:
        return "—"


def post_todays_matches():
    print(f"\n🔄 Bugungi matchlar tekshirilmoqda... {datetime.now()}")

    today = datetime.now().strftime("%Y-%m-%d")
    fixtures = get_fixtures(today)

    if not fixtures:
        print("ℹ️ Bugun match topilmadi")
        return

    filtered = [
        f for f in fixtures
        if f.get("league", {}).get("id") in TOP_LEAGUES
    ]

    if not filtered:
        print("ℹ️ Top ligalarda bugun match yo'q")
        return

    filtered = filtered[:6]

    today_uz = datetime.now().strftime("%d.%m.%Y")
    lines = [f"⚽ BUGUNGI O'YINLAR\n📅 {today_uz}\n"]

    for f in filtered:
        league_id = f["league"]["id"]
        league_name = TOP_LEAGUES.get(league_id, f["league"]["name"])
        home = f["teams"]["home"]["name"]
        away = f["teams"]["away"]["name"]
        kick_off = format_time(f["fixture"]["date"])
        status = f["fixture"]["status"]["short"]

        if status == "FT":
            home_goals = f["goals"]["home"]
            away_goals = f["goals"]["away"]
            lines.append(f"{league_name}")
            lines.append(f"✅ {home} {home_goals} — {away_goals} {away}\n")
        elif status in ["1H", "2H", "HT"]:
            home_goals = f["goals"]["home"]
            away_goals = f["goals"]["away"]
            lines.append(f"{league_name}")
            lines.append(f"🔴 JONLI: {home} {home_goals} — {away_goals} {away}\n")
        else:
            lines.append(f"{league_name}")
            lines.append(f"🕐 {kick_off} | {home} vs {away}\n")

    lines.append("#futbol #bugun #ManSitiPlus")
    post_text = "\n".join(lines)

    send_to_telegram(post_text)


def post_yesterdays_results():
    print(f"\n🔄 Kechagi natijalar tekshirilmoqda... {datetime.now()}")

    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    fixtures = get_fixtures(yesterday, status="FT")

    if not fixtures:
        print("ℹ️ Kecha natija topilmadi")
        return

    filtered = [
        f for f in fixtures
        if f.get("league", {}).get("id") in TOP_LEAGUES
    ]

    if not filtered:
        print("ℹ️ Top ligalarda kecha natija yo'q")
        return

    filtered = filtered[:6]

    yesterday_uz = (datetime.now() - timedelta(days=1)).strftime("%d.%m.%Y")
    lines = [f"📊 KECHAGI NATIJALAR\n📅 {yesterday_uz}\n"]

    for f in filtered:
        league_id = f["league"]["id"]
        league_name = TOP_LEAGUES.get(league_id, f["league"]["name"])
        home = f["teams"]["home"]["name"]
        away = f["teams"]["away"]["name"]
        home_goals = f["goals"]["home"]
        away_goals = f["goals"]["away"]

        if home_goals > away_goals:
            result = f"🏆 {home} {home_goals} — {away_goals} {away}"
        elif away_goals > home_goals:
            result = f"🏆 {away} {away_goals} — {home_goals} {home}"
        else:
            result = f"🤝 {home} {home_goals} — {away_goals} {away}"

        lines.append(f"{league_name}")
        lines.append(f"{result}\n")

    lines.append("#futbol #natijalar #ManSitiPlus")
    post_text = "\n".join(lines)

    send_to_telegram(post_text)


def send_to_telegram(text):
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
        print(f"✅ Post yuborildi: {datetime.now()}")
        return True
    except Exception as e:
        print(f"❌ Telegram xatosi: {e}")
        return False


def run_scheduler():
    print("🚀 Football Bot ishga tushdi!")
    print(f"📢 Kanal: {TELEGRAM_CHANNEL_ID}")
    print("⏰ Har 30 daqiqada yangiliklar tekshiriladi\n")

    schedule.every(30).minutes.do(post_todays_matches)
    schedule.every().day.at("08:00").do(post_yesterdays_results)

    # Darhol birinchi postni yuborish
    post_todays_matches()

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    run_scheduler()
