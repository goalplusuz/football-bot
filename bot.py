import os
import time
import requests
import schedule
from datetime import datetime, timedelta, timezone

# ===================== SOZLAMALAR =====================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "@your_channel")
FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY", "YOUR_FOOTBALL_API_KEY")

# O'zbekiston UTC+5
UZ_OFFSET = timezone(timedelta(hours=5))

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

def now_uz():
    return datetime.now(UZ_OFFSET)


def utc_to_uz(utc_time_str):
    try:
        dt = datetime.fromisoformat(utc_time_str.replace("Z", "+00:00"))
        return dt.astimezone(UZ_OFFSET)
    except:
        return None


def get_fixtures_for_date(date_str):
    """Berilgan UTC sana uchun o'yinlarni olish"""
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


def get_fixtures_in_window(start_uz, end_uz):
    """
    Berilgan vaqt oralig'idagi o'yinlarni olish.
    Masalan: bugun 12:00 - ertaga 03:00 (Toshkent vaqti)
    """
    # UTC sanalarni hisoblash
    start_utc = start_uz.astimezone(timezone.utc)
    end_utc = end_uz.astimezone(timezone.utc)

    # Kerakli UTC sanalar (bir yoki ikki kun bo'lishi mumkin)
    dates_to_fetch = set()
    current = start_utc
    while current <= end_utc:
        dates_to_fetch.add(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)

    # API dan olish
    all_fixtures = []
    for date_str in dates_to_fetch:
        all_fixtures.extend(get_fixtures_for_date(date_str))

    # Filter va dublikat olib tashlash
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

        # Vaqt oralig'ida bo'lgan o'yinlar
        if start_uz <= uz_time <= end_uz:
            f["_uz_time"] = uz_time
            result.append(f)

    # Vaqt bo'yicha tartiblash
    result.sort(key=lambda x: x["_uz_time"])
    return result


def post_todays_matches():
    """
    Bugungi o'yinlar: bugun 12:00 → ertaga 03:00 (Toshkent)
    """
    current = now_uz()
    print(f"\n🔄 Matchlar tekshirilmoqda... {current.strftime('%d.%m.%Y %H:%M')} (Toshkent)")

    # Oynani hisoblash
    today = current.replace(hour=0, minute=0, second=0, microsecond=0)

    # Agar hozir 00:00-11:59 bo'lsa — kechagi 12:00 dan bugun 03:00 gacha
    # Agar hozir 12:00-23:59 bo'lsa — bugun 12:00 dan ertaga 03:00 gacha
    if current.hour < 12:
        window_start = (today - timedelta(days=1)).replace(hour=12, minute=0, second=0)
        window_end = today.replace(hour=3, minute=0, second=0)
    else:
        window_start = today.replace(hour=12, minute=0, second=0)
        window_end = (today + timedelta(days=1)).replace(hour=3, minute=0, second=0)

    fixtures = get_fixtures_in_window(window_start, window_end)
    filtered = [f for f in fixtures if f.get("league", {}).get("id") in TOP_LEAGUES]

    if not filtered:
        print("ℹ️ Top ligalarda o'yin yo'q")
        return

    # Post yaratish
    date_str = window_start.strftime("%d.%m.%Y")
    next_date_str = window_end.strftime("%d.%m")
    lines = [f"⚽ O'YINLAR JADVALI\n📅 {date_str} (12:00) — {next_date_str} (03:00) | Toshkent\n"]
    for f in filtered:
        league_id = f["league"]["id"]
        league_name = TOP_LEAGUES.get(league_id, f["league"]["name"])
        home = f["teams"]["home"]["name"]
        away = f["teams"]["away"]["name"]
        time_str = f["_uz_time"].strftime("%H:%M")
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
    send_to_telegram("\n".join(lines))


def post_yesterdays_results():
    """
    Kechagi natijalar: kecha 12:00 → bugun 03:00 oralig'ida tugagan o'yinlar
    """
    current = now_uz()
    today = current.replace(hour=0, minute=0, second=0, microsecond=0)

    window_start = (today - timedelta(days=1)).replace(hour=12, minute=0, second=0)
    window_end = today.replace(hour=3, minute=0, second=0)

    print(f"\n🔄 Kechagi natijalar... {current.strftime('%d.%m.%Y %H:%M')} (Toshkent)")

    fixtures = get_fixtures_in_window(window_start, window_end)
    filtered = [
        f for f in fixtures
        if f.get("league", {}).get("id") in TOP_LEAGUES
        and f["fixture"]["status"]["short"] == "FT"
    ]

    if not filtered:
        print("ℹ️ Kecha top ligalarda natija yo'q")
        return

    yesterday_str = (today - timedelta(days=1)).strftime("%d.%m.%Y")
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
    send_to_telegram("\n".join(lines))


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

    # Har kuni soat 12:00 da bugungi jadval
    schedule.every().day.at("12:00").do(post_todays_matches)

    # Har kuni soat 09:00 da kechagi natijalar
    schedule.every().day.at("09:00").do(post_yesterdays_results)

    post_todays_matches()

    while True:
        schedule.run_pending()
        time.sleep(60)


if name == "main":
    run_scheduler()
