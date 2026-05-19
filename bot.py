import os
import json
import time
import requests
import schedule
from datetime import datetime, timedelta
import pytz

# ===================== SOZLAMALAR =====================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "@your_channel")
FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY", "YOUR_FOOTBALL_API_KEY")

UZ_TZ = pytz.timezone("Asia/Tashkent")

TOP_LEAGUES = {
    2: "🏆 UEFA Champions League",
    3: "🥈 UEFA Europa League",
    39: "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League",
    140: "🇪🇸 La Liga",
    135: "🇮🇹 Serie A",
    78: "🇩🇪 Bundesliga",
    61: "🇫🇷 Ligue 1",
    4: "🌍 UEFA Nations League",
    1: "🌐 FIFA World Cup",
}

# ======================================================

def get_fixtures_for_date(date_str):
    """Berilgan sana uchun o'yinlarni olish (UTC sana)"""
    url = "https://v3.football.api-sports.io/fixtures"
    headers = {"x-apisports-key": FOOTBALL_API_KEY}
    params = {"date": date_str}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("response", [])
    except Exception as e:
        print(f"❌ API xatosi: {e}")
        return []


def utc_to_uz(utc_time_str):
    """UTC vaqtni O'zbekiston vaqtiga o'tkazish"""
    try:
        dt = datetime.fromisoformat(utc_time_str.replace("Z", "+00:00"))
        uz_time = dt.astimezone(UZ_TZ)
        return uz_time
    except:
        return None


def get_todays_fixtures():
    """
    O'zbekiston vaqti bo'yicha "bugun" bo'lgan barcha o'yinlar.
    Masalan: O'zbekistonda bugun 00:00 - 23:59 orasidagi o'yinlar.
    Bu UTC da kecha 19:00 - bugun 18:59 ga to'g'ri keladi.
    """
    now_uz = datetime.now(UZ_TZ)
    today_uz_start = now_uz.replace(hour=0, minute=0, second=0, microsecond=0)
    today_uz_end = now_uz.replace(hour=23, minute=59, second=59, microsecond=0)

    # UTC sanalar (O'zbekiston UTC+5)
    utc_start = today_uz_start.astimezone(pytz.utc)
    utc_end = today_uz_end.astimezone(pytz.utc)

    # API dan ikkita sana uchun olish (kecha UTC va bugun UTC)
    dates_to_fetch = set()
    dates_to_fetch.add(utc_start.strftime("%Y-%m-%d"))
    dates_to_fetch.add(utc_end.strftime("%Y-%m-%d"))

    all_fixtures = []
    for date_str in dates_to_fetch:
        all_fixtures.extend(get_fixtures_for_date(date_str))

    # Faqat O'zbekiston "bugun"iga to'g'ri keladiganlarni filter
    result = []
    seen_ids = set()
    for f in all_fixtures:
        fid = f["fixture"]["id"]
        if fid in seen_ids:
            continue
        seen_ids.add(fid)

        uz_time = utc_to_uz(f["fixture"]["date"])
        if uz_time is None:
            continue

        if today_uz_start <= uz_time <= today_uz_end:
            f["_uz_time"] = uz_time
            result.append(f)

    # Vaqt bo'yicha tartiblash
    result.sort(key=lambda x: x["_uz_time"])
    return result


def get_yesterdays_results():
    """O'zbekiston vaqti bo'yicha kecha tugagan o'yinlar"""
    now_uz = datetime.now(UZ_TZ)
    yesterday_uz_start = (now_uz - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_uz_end = (now_uz - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=0)

    utc_start = yesterday_uz_start.astimezone(pytz.utc)
    utc_end = yesterday_uz_end.astimezone(pytz.utc)

    dates_to_fetch = set()
    dates_to_fetch.add(utc_start.strftime("%Y-%m-%d"))
    dates_to_fetch.add(utc_end.strftime("%Y-%m-%d"))

    all_fixtures = []
    for date_str in dates_to_fetch:
        all_fixtures.extend(get_fixtures_for_date(date_str))

    result = []
    seen_ids = set()
    for f in all_fixtures:
        fid = f["fixture"]["id"]
        if fid in seen_ids:
            continue
        seen_ids.add(fid)

        uz_time = utc_to_uz(f["fixture"]["date"])
        if uz_time is None:
            continue

        status = f["fixture"]["status"]["short"]
        if status == "FT" and yesterday_uz_start <= uz_time <= yesterday_uz_end:
            f["_uz_time"] = uz_time
            result.append(f)

    result.sort(key=lambda x: x["_uz_time"])
    return result


def post_todays_matches():
    now_uz = datetime.now(UZ_TZ)
    print(f"\n🔄 Bugungi matchlar tekshirilmoqda... {now_uz.strftime('%d.%m.%Y %H:%M')} (Toshkent)")

    fixtures = get_todays_fixtures()

    filtered = [f for f in fixtures if f.get("league", {}).get("id") in TOP_LEAGUES]

    if not filtered:
        print("ℹ️ Top ligalarda bugun match yo'q")
        return

    filtered = filtered[:6]
    today_str = now_uz.strftime("%d.%m.%Y")
    lines = [f"⚽ BUGUNGI O'YINLAR\n📅 {today_str} | 🕐 Toshkent vaqti\n"]

    for f in filtered:
        league_id = f["league"]["id"]
        league_name = TOP_LEAGUES.get(league_id, f["league"]["name"])
        home = f["teams"]["home"]["name"]
        away = f["teams"]["away"]["name"]
        uz_time = f["_uz_time"]
        time_str = uz_time.strftime("%H:%M")
        status = f["fixture"]["status"]["short"]

        if status == "FT":
            hg = f["goals"]["home"]
            ag = f["goals"]["away"]
            lines.append(f"{league_name}")
            lines.append(f"✅ {home} {hg} — {ag} {away}\n")
        elif status in ["1H", "2H", "HT", "ET", "P"]:
            hg = f["goals"]["home"]
            ag = f["goals"]["away"]
            elapsed = f["fixture"]["status"].get("elapsed", "")
            lines.append(f"{league_name}")
            lines.append(f"🔴 JONLI {elapsed}' | {home} {hg} — {ag} {away}\n")
        else:
            lines.append(f"{league_name}")
            lines.append(f"🕐 {time_str} | {home} vs {away}\n")

    lines.append("#futbol #bugun #ManSitiPlus")
    post_text = "\n".join(lines)
    send_to_telegram(post_text)


def post_yesterdays_results():
    now_uz = datetime.now(UZ_TZ)
    print(f"\n🔄 Kechagi natijalar tekshirilmoqda... {now_uz.strftime('%d.%m.%Y %H:%M')} (Toshkent)")

    fixtures = get_yesterdays_results()
    filtered = [f for f in fixtures if f.get("league", {}).get("id") in TOP_LEAGUES]

    if not filtered:
        print("ℹ️ Top ligalarda kecha natija yo'q")
        return

    filtered = filtered[:6]
    yesterday_str = (now_uz - timedelta(days=1)).strftime("%d.%m.%Y")
    lines = [f"📊 KECHAGI NATIJALAR\n📅 {yesterday_str}\n"]

    for f in filtered:
        league_id = f["league"]["id"]
        league_name = TOP_LEAGUES.get(league_id, f["league"]["name"])
        home = f["teams"]["home"]["name"]
        away = f["teams"]["away"]["name"]
        hg = f["goals"]["home"]
        ag = f["goals"]["away"]

        if hg > ag:
            result = f"🏆 {home} {hg} — {ag} {away}"
        elif ag > hg:
            result = f"🏆 {away} {ag} — {hg} {home}"
        else:
            result = f"🤝 {home} {hg} — {ag} {away}"

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
        print(f"✅ Post yuborildi!")
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

    post_todays_matches()

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    run_scheduler()
