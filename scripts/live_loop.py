#!/usr/bin/env python3
"""Maç saatlerinde birkaç dakikada bir skorları ve puan durumunu repoya yazar.

Site canlı veriyi önce doğrudan ESPN'den okumaya çalışır. ESPN tarayıcıya
cevap vermezse bu döngünün yazdığı data/scoreboard.json dosyasını kullanır.

Döngü, oynanan ya da 90 dakika içinde başlayacak maç kalmayınca kendiliğinden
biter. GitHub Actions'ta "Canlı mod" görevi tarafından çalıştırılır.
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import update_standings as us  # noqa: E402

INTERVAL = 4 * 60          # saniye
MAX_RUNTIME = 5.5 * 3600   # GitHub görev süresi sınırının altında kal
SOON = timedelta(minutes=90)


def git(*args):
    return subprocess.run(["git", *args], cwd=us.ROOT, capture_output=True, text=True)


def commit_if_changed():
    if git("diff", "--quiet", "--", "data/").returncode == 0:
        return False
    git("add", "data/")
    git("commit", "-m", "Canlı skor güncellemesi")
    push = git("push")
    if push.returncode != 0:  # araya başka commit girdiyse üstüne al ve tekrar dene
        git("pull", "--rebase", "-X", "theirs")
        git("push")
    return True


def keep_going(games) -> bool:
    now = datetime.now(timezone.utc)
    for g in games:
        if g.get("seasonType") == 1:  # hazırlık maçları sayılmaz
            continue
        if g["state"] == "in":
            return True
        if g["state"] == "pre":
            start = datetime.fromisoformat(g["start"].replace("Z", "+00:00"))
            if start - now <= SOON:
                return True
    return False


def main():
    t0 = time.time()
    while True:
        try:
            us.update()
            games = us.update_scoreboard()
        except Exception as exc:
            print(f"Veri alınamadı: {exc}", file=sys.stderr)
            games = []
        if commit_if_changed():
            print(datetime.now(timezone.utc).strftime("%H:%M"), "güncellendi")
        if not keep_going(games):
            print("Oynanan ya da yakında başlayacak maç yok, döngü bitti.")
            return 0
        if time.time() - t0 > MAX_RUNTIME:
            print("Süre sınırına gelindi.")
            return 0
        time.sleep(INTERVAL)


if __name__ == "__main__":
    sys.exit(main())
