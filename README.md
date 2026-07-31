# Sezonowość — backtest

Osobny projekt (świadomie **oddzielony od vtrade-stats**: tam są statystyki
live, tu backtest). Miesięczny P&L portfela naszych botów z backtestu
championów, w układzie **rok × miesiąc**, do porównania z cyklicznością
**COT** i **Larry'ego Williamsa**.

## Co pokazuje `index.html`

- **Macierz rok × miesiąc** — suma € miesięcznego P&L portfela (każdy bot na
  bazie 10 000, ryzyko wg `USTAWIENIA_FORWARD.txt`). W każdej komórce:
  net € (góra) + **▼max DD konta w tym miesiącu** (obsunięcie wewnątrzmiesięczne).
- **Σ / miesiąc** i **Śr / miesiąc** — nasz *odcisk sezonowy* (średnia po latach).
- **Nakładki referencyjne** (nie nasz wynik), wyrównane do kolumn miesięcy:
  - **LW** — cykle Larry Williams Forecast 2026 (long/short/ostrożność per rynek).
  - **COT** — sezonowa zmiana pozycji NET dużych spekulantów (CFTC), złoto od
    1986, Nasdaq/JPY od 2000.
- **Wkład roczny per bot**.

## Ograniczenie (uczciwie)

Dane brokera (m1) sięgają ~2023 → macierz to **~3,5 roku** (3–4 próbki na
miesiąc kalendarzowy). To **cross-check**, nie twardy wzorzec sezonowy —
głębszą historię dają właśnie nakładki COT/LW.

## Pipeline

```
monthly_bt.py   → data/monthly_bt_results.json   (backtest per rok, 11 botów, przez G2BacktestServer:9877)
cot_fetch.py    → data/cot_seasonal.json          (CFTC Socrata, publicreporting.cftc.gov)
lw_parse.py     → data/lw_seasonal.json           (z ...\01_MATERIALY\02_LARRY_WILLIAMS_2026\...xlsx)
build_report.py → index.html                       (składa wszystko w raport)
```

Uruchomienie (po policzeniu danych):

```bash
python build_report.py      # → index.html (otwórz w przeglądarce)
```

Regeneracja danych:

```bash
python monthly_bt.py        # wymaga uruchomionego cTradera + G2BacktestServer na 9877 (resume per bot/rok)
python cot_fetch.py         # internet (CFTC)
python lw_parse.py          # kalendarz LW (xlsx)
```

## Uwagi

- `monthly_bt.py` importuje `ppk_grid` (api/extract) z `..\hts_loop` (sys.path).
- Configi championów = 1:1 z `hts_loop\FORWARD_962\USTAWIENIA_FORWARD.txt`
  (6 zwalidowanych + 5 wyprowadzonych z `.cs`, walidowane względem benchmarków).
- `index.html` jest samodzielny (dark, bez zależności) — można go hostować
  (GitHub Pages / lokalnie). Domyślnie NIE publikowany.
