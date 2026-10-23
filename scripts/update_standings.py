#!/usr/bin/env python3
"""NBA puan durumunu ESPN'den çekip data/ klasörüne kaydeder.

Üretilen dosyalar:
  data/standings.json  Güncel puan durumu (sitenin yedek kaynağı; site canlı
                       veriyi doğrudan ESPN'den okur, ulaşamazsa bunu kullanır)
  data/history.json    Her gün için takımların galibiyet-mağlubiyet kaydı.
                       "Hareketler" sekmesi ve "YENİ" rozeti bunu kullanır.

Kullanım:
  python scripts/update_standings.py              # normal güncelleme
  python scripts/update_standings.py --backfill   # sezon başından geçmişi kur

Sadece Python standart kütüphanesi kullanılır.
"""
import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
STANDINGS_OUT = os.path.join(DATA, "standings.json")
HISTORY_OUT = os.path.join(DATA, "history.json")

BASE = "https://site.api.espn.com/apis"
STANDINGS_URL = BASE + "/v2/sports/basketball/nba/standings?season={season}"
TEAMS_URL = BASE + "/site/v2/sports/basketball/nba/teams"
SCOREBOARD_URL = BASE + "/site/v2/sports/basketball/nba/scoreboard?dates={d}&limit=50"
GAMES_PER_SEASON = 82
TR = timezone(timedelta(hours=3))  # Türkiye saati


def get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "nba-bahis-takip/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def current_season() -> int:
    """ESPN sezonu bitiş yılıyla adlandırır (2026-27 sezonu = 2027)."""
    now = datetime.now(timezone.utc)
    return now.year + 1 if now.month >= 8 else now.year


def team_colors() -> dict:
    try:
        raw = get(TEAMS_URL)
        teams = raw["sports"][0]["leagues"][0]["teams"]
        return {
            t["team"]["abbreviation"]: {
                "color": "#" + t["team"].get("color", "777777"),
                "alt": "#" + t["team"].get("alternateColor", "aaaaaa"),
            }
            for t in teams
        }
    except Exception as exc:  # renkler olmazsa da site çalışır
        print(f"Takım renkleri alınamadı: {exc}", file=sys.stderr)
        return {}


def parse_standings(raw: dict, colors: dict) -> list:
    teams = []
    for conf in raw.get("children", []):
        conf_name = conf.get("abbreviation", "")
        for entry in conf.get("standings", {}).get("entries", []):
            t = entry["team"]
            stats = {s["name"]: s for s in entry.get("stats", [])}

            def val(key, default=0):
                v = stats.get(key, {}).get("value")
                return v if v is not None else default

            logo = next(
                (l["href"] for l in t.get("logos", []) if "default" in l.get("rel", [])), ""
            )
            c = colors.get(t["abbreviation"], {})
            teams.append(
                {
                    "abbr": t["abbreviation"],
                    "name": t["displayName"],
                    "short": t.get("shortDisplayName", t["displayName"]),
                    "conference": conf_name,
                    "logo": logo,
                    "color": c.get("color", ""),
                    "altColor": c.get("alt", ""),
                    "wins": int(val("wins")),
                    "losses": int(val("losses")),
                    "seed": int(val("playoffSeed", 0)),
                    "gb": stats.get("gamesBehind", {}).get("displayValue", "-"),
                    "pct": round(float(val("winPercent", 0)), 3),
                    "streak": stats.get("streak", {}).get("displayValue", ""),
                    "last10": stats.get("Last Ten Games", {}).get("displayValue", ""),
                    "home": stats.get("Home", {}).get("displayValue", ""),
                    "road": stats.get("Road", {}).get("displayValue", ""),
                }
            )
    teams.sort(key=lambda x: x["abbr"])
    return teams


def load_json(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1 if path == HISTORY_OUT else 2)
        f.write("\n")


def update() -> int:
    season = current_season()
    teams = parse_standings(get(STANDINGS_URL.format(season=season)), team_colors())
    if len(teams) != 30:
        print(f"Beklenmeyen takım sayısı: {len(teams)} — dosyalar güncellenmedi.", file=sys.stderr)
        return 1

    payload = {
        "season": season,
        "seasonLabel": f"{season - 1}-{str(season)[-2:]}",
        "gamesPerSeason": GAMES_PER_SEASON,
        "teams": teams,
    }
    old = load_json(STANDINGS_OUT, {})
    if {k: v for k, v in old.items() if k != "updatedAt"} != payload:
        payload["updatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        save_json(STANDINGS_OUT, payload)
        print(f"Puan durumu güncellendi ({payload['seasonLabel']}).")
    else:
        print("Puan durumunda değişiklik yok.")

    # Günlük geçmiş: Türkiye tarihine göre o günün son durumu
    hist = load_json(HISTORY_OUT, {"season": season, "days": {}})
    if hist.get("season") != season:
        hist = {"season": season, "days": {}}
    today = datetime.now(TR).date().isoformat()
    snap = {t["abbr"]: [t["wins"], t["losses"]] for t in teams}
    if hist["days"].get(today) != snap:
        hist["days"][today] = snap
        hist["days"] = dict(sorted(hist["days"].items()))
        save_json(HISTORY_OUT, hist)
        print(f"Geçmiş kaydı güncellendi ({today}).")
    return 0


def backfill() -> int:
    """Sezon başından bugüne her günün sonundaki kaydı maç sonuçlarından kurar.

    ABD'de D günü oynanan maçlar Türkiye saatiyle D+1 sabahı biter; bu yüzden
    D gününün sonuçları D+1 tarihli kayda yazılır.
    """
    season = current_season()
    start = date(season - 1, 10, 1)
    end = datetime.now(TR).date()
    rec = {}
    days = {}
    d = start
    started = False
    while d < end:
        sb = get(SCOREBOARD_URL.format(d=d.strftime("%Y%m%d")))
        for ev in sb.get("events", []):
            if ev.get("season", {}).get("type") != 2:  # sadece normal sezon
                continue
            if ev["status"]["type"].get("state") != "post":
                continue
            started = True
            for c in ev["competitions"][0]["competitors"]:
                a = c["team"]["abbreviation"]
                w, l = rec.get(a, [0, 0])
                rec[a] = [w + 1, l] if c.get("winner") else [w, l + 1]
        if started:
            key = (d + timedelta(days=1)).isoformat()
            days[key] = {a: list(v) for a, v in sorted(rec.items())}
        d += timedelta(days=1)
    hist = {"season": season, "days": days}
    save_json(HISTORY_OUT, hist)
    print(f"Geçmiş kuruldu: {len(days)} gün.")
    return update()


SCOREBOARD_OUT = os.path.join(DATA, "scoreboard.json")


def parse_games(raw: dict) -> list:
    games = []
    for ev in raw.get("events", []):
        c = ev["competitions"][0]
        st = ev.get("status", {})
        ty = st.get("type", {})

        def side(k):
            x = next((p for p in c["competitors"] if p.get("homeAway") == k), {})
            t = x.get("team", {})
            score = x.get("score")
            return {
                "abbr": t.get("abbreviation"),
                "name": t.get("shortDisplayName"),
                "logo": t.get("logo"),
                "score": int(score) if score not in (None, "") else None,
                "winner": bool(x.get("winner")),
                "rec": (x.get("records") or [{}])[0].get("summary", ""),
            }

        games.append(
            {
                "id": ev["id"],
                "start": ev["date"],
                "state": ty.get("state"),
                "completed": bool(ty.get("completed")),
                "detail": ty.get("shortDetail", ""),
                "period": st.get("period", 0),
                "clock": st.get("displayClock", ""),
                "typeName": ty.get("name", ""),
                "home": side("home"),
                "away": side("away"),
                "seasonType": ev.get("season", {}).get("type"),
            }
        )
    return games


def update_scoreboard() -> list:
    raw = get(BASE + "/site/v2/sports/basketball/nba/scoreboard")
    day = (raw.get("day", {}).get("date") or "").replace("-", "")
    games = parse_games(raw)
    payload = {"day": day, "games": games}
    old = load_json(SCOREBOARD_OUT, {})
    if {k: v for k, v in old.items() if k != "updatedAt"} != payload:
        payload["updatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        save_json(SCOREBOARD_OUT, payload)
    return games


if __name__ == "__main__":
    if "--backfill" in sys.argv:
        sys.exit(backfill())
    code = update()
    try:
        update_scoreboard()
    except Exception as exc:
        print(f"Maç skorları alınamadı: {exc}", file=sys.stderr)
    sys.exit(code)
