# -*- coding: utf-8 -*-
"""Sciaga COT (CFTC Legacy Futures-Only, Socrata) dla rynkow naszych botow i
liczy SEZONOWA zmiane pozycji duzych spekulantow (non-commercial NET) per
miesiac kalendarzowy -> cot_seasonal.json (nakladka do vtrade-stats).

Metoda: net = noncomm_long - noncomm_short (tygodniowo) -> koniec miesiaca ->
zmiana m/m -> per miesiac kalendarzowy: srednia zmiana + % lat, w ktorych
spekulanci DODAWALI netto (bias byczy). To sezonowosc POZYCJONOWANIA, nie ceny.

Zrodlo: https://publicreporting.cftc.gov (dataset 6dca-aqww, Legacy Futures Only).
"""
import json
import sys
import urllib.parse
import urllib.request
from collections import defaultdict

for s in (sys.stdout, sys.stderr):
    try: s.reconfigure(encoding="utf-8")
    except Exception: pass

BASE = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
OUT = r"Y:\15_AI\02_TRADING\sezonowosc_backtest\data\cot_seasonal.json"

MARKETS = {
    "gold":   ("Złoto (COMEX GC)",        "GOLD - COMMODITY EXCHANGE INC."),
    "nasdaq": ("Nasdaq-100 (E-mini CME)", "NASDAQ-100 STOCK INDEX (MINI) - CHICAGO MERCANTILE EXCHANGE"),
    "jpy":    ("Jen japoński (CME)",      "JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE"),
}
FIELDS = ("report_date_as_yyyy_mm_dd,noncomm_positions_long_all,"
          "noncomm_positions_short_all,comm_positions_long_all,comm_positions_short_all")


def fetch(market_name):
    q = {"$select": FIELDS,
         "$where": f"market_and_exchange_names = '{market_name}'",
         "$order": "report_date_as_yyyy_mm_dd",
         "$limit": "60000"}
    url = BASE + "?" + urllib.parse.urlencode(q)
    with urllib.request.urlopen(url, timeout=90) as r:
        return json.loads(r.read().decode())


def monthly_seasonal(rows):
    # koniec-miesiaca net (ostatni raport w miesiacu)
    month_end = {}  # 'YYYY-MM' -> net
    for row in rows:
        d = row.get("report_date_as_yyyy_mm_dd", "")[:10]
        if len(d) < 7:
            continue
        try:
            nl = float(row["noncomm_positions_long_all"]); ns = float(row["noncomm_positions_short_all"])
        except (KeyError, ValueError, TypeError):
            continue
        month_end[d[:7]] = nl - ns  # kolejne raporty nadpisuja -> zostaje ostatni
    keys = sorted(month_end)
    # zmiana m/m przypisana do miesiaca docelowego, tylko sasiadujace miesiace
    changes = defaultdict(list)  # month(1..12) -> [zmiany]
    for i in range(1, len(keys)):
        y0, m0 = map(int, keys[i - 1].split("-"))
        y1, m1 = map(int, keys[i].split("-"))
        if (y1 * 12 + m1) - (y0 * 12 + m0) != 1:
            continue  # luka -> nie licz sztucznej zmiany
        changes[m1].append(month_end[keys[i]] - month_end[keys[i - 1]])
    sig, pct_up, mean_chg, nyears = [], [], [], []
    for m in range(1, 13):
        ch = changes.get(m, [])
        if not ch:
            sig.append(None); pct_up.append(None); mean_chg.append(None); nyears.append(0); continue
        mean = sum(ch) / len(ch)
        up = sum(1 for x in ch if x > 0) / len(ch)
        # bias: potrzeba i znaku sredniej i wiekszosci lat zgodnych
        if mean > 0 and up >= 0.55: s = "long"
        elif mean < 0 and up <= 0.45: s = "short"
        else: s = "neutral"
        sig.append(s); pct_up.append(round(up * 100)); mean_chg.append(round(mean)); nyears.append(len(ch))
    span = f"{keys[0]}..{keys[-1]}" if keys else "?"
    return {"sig": sig, "pct_up": pct_up, "mean_chg": mean_chg, "nyears": nyears, "span": span}


def main():
    markets = {}
    for k, (label, name) in MARKETS.items():
        try:
            rows = fetch(name)
            seas = monthly_seasonal(rows)
            markets[k] = {"label": label, "cftc_name": name, **seas}
            print(f"{k:7} {label}: {len(rows)} raportow, span {seas['span']}", flush=True)
            print(f"        sig: {seas['sig']}", flush=True)
        except Exception as e:
            markets[k] = {"label": label, "cftc_name": name, "error": str(e)}
            print(f"{k:7} ERROR {e}", flush=True)
    out = {"source": "CFTC Commitments of Traders — Legacy Futures Only (publicreporting.cftc.gov, 6dca-aqww)",
           "metric": "sezonowa zmiana m/m pozycji NET dużych spekulantów (non-commercial long-short)",
           "months": ["Sty", "Lut", "Mar", "Kwi", "Maj", "Cze", "Lip", "Sie", "Wrz", "Paź", "Lis", "Gru"],
           "markets": markets}
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\nOK ->", OUT)


if __name__ == "__main__":
    main()
