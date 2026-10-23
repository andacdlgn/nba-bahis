# Alt / Üst Takibi — Andaç vs Mustafa

NBA 2026-27 sezonu öncesi galibiyet baremlerine verilen alt/üst tahminlerini canlı takip eden site.

## Nasıl çalışır
- `index.html`: Site. `data/` klasöründeki iki dosyayı okuyup tabloyu ve skoru hesaplar.
- `data/picks.json`: Baremler ve seçimler. **Elle doldurulan tek dosya bu.**
- `data/standings.json`: Güncel puan durumu. GitHub Actions bunu otomatik günceller, elle dokunmaya gerek yok.
- `data/history.json`: Her günün galibiyet-mağlubiyet kaydı. Hareketler sekmesi ve "YENİ" rozeti bunu kullanır.
- `data/scoreboard.json`: Günün maçları. Telefon ESPN'e doğrudan ulaşamazsa site bunu okur.
- `scripts/update_standings.py`: ESPN'den puan durumunu, maçları ve geçmişi çeken betik.
- `scripts/live_loop.py`: Maç saatlerinde 4 dakikada bir güncelleyen döngü.
- `.github/workflows/update-standings.yml`: Her 2 saatte bir genel güncelleme.
- `.github/workflows/live.yml`: Her gece 01:50'de (TR) başlayan canlı mod; maçlar bitince durur.

## Canlı veri nasıl geliyor
1. Site açıkken skorları ve puan durumunu doğrudan ESPN'den çeker (maç varken 30 sn, yokken 5 dk).
2. ESPN'e ulaşılamazsa GitHub'daki `data/` dosyalarını okur (canlı modda birkaç dakika gecikmeli).
3. Sekmenin sağ üstünde hangi kaynağın kullanıldığı yazar: "Canlı" ya da "Birkaç dk gecikmeli".

## Seçimleri girmek
`data/picks.json` içinde her takım için:

```json
"BOS": { "takim": "Boston Celtics", "barem": 52.5, "andac": "ust", "mustafa": "alt" }
```

Seçim değerleri `"ust"` ya da `"alt"`.

## Yayına alma (bir kez)
1. Repo → **Settings → Pages** → Source: *Deploy from a branch*, Branch: `main`, klasör `/ (root)` → Save.
2. Repo → **Settings → Actions → General** → *Workflow permissions*: **Read and write permissions** → Save.
3. **Actions** sekmesi → "Puan durumunu güncelle" → **Run workflow** ile ilk güncellemeyi elle tetikle.

Birkaç dakika içinde site `https://<kullanıcı-adı>.github.io/<repo-adı>/` adresinde açılır.

## Kurallar
- Takımın galibiyet sayısı baremi geçtiği anda ÜST kesinleşir. Kalan maçların hepsini kazansa bile bareme ulaşamayacaksa ALT kesinleşir.
- "Gidişat" puanı, takımın şu anki kazanma yüzdesiyle 82 maça yayılan tempoya göre hesaplanır.
- Baremler buçuklu olduğu için berabere durumu yok.
