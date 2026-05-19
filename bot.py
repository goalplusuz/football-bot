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
