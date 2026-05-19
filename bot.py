import os
import json
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
    """Hozirgi O'zbekiston vaqti"""
    return datetime.now(UZ_OFFSET)


def utc_to_uz(utc_time_str):
    """UTC vaqtni O'zbekiston vaqtiga o'tkazish"""
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


def get_fixtures_in_uz_day(uz_day_offset=0):
    """
    O'zbekiston vaqti bo'yicha berilgan kun (0=bugun, -1=kecha) o'yinlarini olish.
    Masalan bugun 00:00-23:59 Toshkent = kecha 19:00 - bugun 18:59 UTC
    """
    target_uz = now_uz() + timedelta(days=uz_day_offset)
    day_start_uz = target_uz.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end_uz = target_uz.replace(hour=23, minute=59, second=59, microsecond=0)

    # UTC sanalar
    day_start_utc = day_start_uz.astimezone(timezone.utc)
    day_end_utc = day_end_uz.astimezone(timezone.utc)

    # Ikkita UTC sana bo'lishi mumkin (masalan 19:00 UTC = kecha + bugun)
    dates_to_fetch = set()
    dates_to_fetch.add(day_start_utc.strftime("%Y-%m-%d"))
    dates_to_fetch.add(day_end_utc.strftime("%Y-%m-%d"))

    all_fixtures = []
    for date_str in dates_to_fetch:
        all_fixtures.extend(get_fixtures_for_date(date_str))

    # Dublikatlarni olib tashlash va O'zbekiston kuniga filter
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

        if day_start_uz <= uz_time <= day_end_uz:
            f["_uz_time"] = uz_time
            result.append(f)

    result.sort(key=lambda x: x["_uz_time"])
    return result


def post_todays_matches():
    current = now_uz()
    print(f"\n🔄 Bugungi matchlar... {current.strftime('%d.%m.%Y %H:%M')} (Toshkent)")

    fixtures = get_fixtures_in_uz_day(0)
    filtered = [f for f in fixtures if f.get("league", {}).get("id") in TOP_LEAGUES]

    if not filtered:
        print("ℹ️ Top ligalarda bugun match yo'q")
        return

    filtered = filtered[:6]
    today_str = current.strftime("%d.%m.%Y")
    lines = [f"⚽ BUGUNGI O'YINLAR\n📅 {today_str} | 🕐 Toshkent vaqti\n"]

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
    current = now_uz()
    print(f"\n🔄 Kechagi natijalar... {current.strftime('%d.%m.%Y %H:%M')} (Toshkent)")

    fixtures = get_fixtures_in_uz_day(-1)
    filtered = [
        f for f in fixtures
        if f.get("league", {}).get("id") in TOP_LEAGUES
        and f["fixture"]["status"]["short"] == "FT"
    ]

    if not filtered:
        print("ℹ️ Top ligalarda kecha natija yo'q")
        return

    filtered = filtered[:6]
    yesterday_str = (now_uz() - timedelta(days=1)).strftime("%d.%m.%Y")
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
    schedule.every().day.at("08:00").do(post_yesterdays_results)

    post_todays_matches()

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    run_scheduler()
