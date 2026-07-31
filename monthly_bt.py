# -*- coding: utf-8 -*-
"""monthly_bt.py — backtest wszystkich strumieni PER ROK (do dna danych brokera),
transakcje pociete na miesiace (RRRR-MM) z history.items.

Cel: macierz rok x miesiac (suma P&L portfela) do porownania z sezonowoscia
COT / Larry Williamsa. Configi 1:1 z USTAWIENIA_FORWARD.txt (championy).

Dlaczego PER ROK, nie 1 run pelnej historii:
  - GER40 na dataMode m1 przez 3,5 roku = timeout (za duzo danych m1). Per rok
    kazdy run 4x krotszy -> miesci sie (maxbt_all tak liczyl, zwalidowane).
  - Baza 10k STALA co roku (nie kompletowana) -> € kazdego miesiaca bezposrednio
    porownywalne miedzy latami. To wlasnie chcemy do sezonowosci.

Dane brokera: m1 od ~2023-01 -> realnie 2023..2026H1 (~3,5 roku). Malo probek na
miesiac — cross-check, nie twardy wzorzec.

Zapis przyrostowy do monthly_bt_results.json. RESUME per (bot, rok): segment juz
policzony (bez bledu) jest pomijany. --force liczy od zera.
"""
import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, "Y:/15_AI/02_TRADING/hts_loop")  # ppk_grid (api/extract)
from ppk_grid import api, extract

OUT = "Y:/15_AI/02_TRADING/sezonowosc_backtest/data/monthly_bt_results.json"

SEGS = [("2023", "2023-01-02", "2024-01-01"),
        ("2024", "2024-01-01", "2025-01-01"),
        ("2025", "2025-01-01", "2026-01-01"),
        ("2026H1", "2026-01-01", "2026-07-25")]

# --- configi championow (6 zwalidowanych 1:1 z maxbt_all.py) ---
GDEP = [33,"Simple",5,0,10.0,2.0,True,21,2.0,False,2.0,1,False,8,0,17,20,True,
        0.0,0.0,False,150,70,"both","close",False,"h4"]
DAXL = [33,"Simple",5,0,10.0,1.0,True,21,2.0,False,2.0,1,True,8,0,17,20,True,
        0.0,0.0,False,150,70,"long","close",False,"h4"]
GRT  = [33,144,"Simple","h4",2,10.0,1.0,True,21,2.0,False,2.0,1,"both"]
JPY  = [33,144,"Simple","h12",99,10.0,1.0,True,21,2.0,False,2.0,1,"both","auto"]
ORB  = ["08:00","17:20",15,"wicks",False,0,0.0,0.0,0.0,3.0,2.0,True,2.0,True,
        False,21,2.0,1,"both",False]
OLB  = ["08:00","17:20",60,"wicks",False,0,0.0,0.0,0.0,3.0,1.0,True,1.0,True,
        False,21,2.0,1,"long",False]
# --- 5 wyprowadzonych z .cs (kolejnosc [Parameter]) + USTAWIENIA_FORWARD ---
TRR = [8,50.0,2,50.0,90.0,2,False,75.0,True,"01:00",60,False,20,45,True,60,1.0,
       50.0,0.05,3.0,1.0,"halfmove",2.0,2,False]
PPK = [1.5,24,"band","both",1.0,14,0.5,False,1,True,33,144,3.0]
BTFD = ["ny","14:30","21:00",3,14,2.0,10,1.0,False]
RSI = [2,5,95,200,5,10,1.0,3.0,14,1.0,"both",1,False]
TURTLE = [55,20,20,2.0,False,0,1.0,"both",2.0,1,False]

# tag, nazwa PL, robot, symbol, tf-wykresu, spread(pips), params
STREAMS = [
    ("gdep",   "Złoto DEP",        "HtsLabBot",       "XAUUSD", "h1",  20.0, GDEP),
    ("daxl",   "DAX Sesja",        "HtsLabBot",       "GER40",  "h1",  15.0, DAXL),
    ("grt",    "Złoto RT-HTF",     "RtHtfBot",        "XAUUSD", "m15", 20.0, GRT),
    ("jpy",    "JPY Adaptacja",    "RtAdaptiveBot",   "USDJPY", "m15",  2.0, JPY),
    ("orb",    "DAX ORB",          "OrbBot",          "GER40",  "m5",  15.0, ORB),
    ("olb",    "DAX London Break", "OrbLbBot",        "GER40",  "m5",  15.0, OLB),
    ("trr",    "Złoto Okno Azji",  "TrrBot",          "XAUUSD", "m1",  20.0, TRR),
    ("ppk",    "US100 PPK-Rev",    "PpkRevBot",       "US100",  "m5",  15.0, PPK),
    ("btfd",   "US100 BTFD (LW)",  "BtfdBot",         "US100",  "m5",  15.0, BTFD),
    ("rsi",    "US100 RSI2-Rev",   "RsiReversionBot", "US100",  "d1",  15.0, RSI),
    ("turtle", "Złoto Turtle S2",  "TurtleBot",       "XAUUSD", "d1",  20.0, TURTLE),
]


def run_seg(robot, sym, tf, spread, params, frm, to, timeout_s=2400, retries=1):
    body = {"robot": robot, "symbol": sym, "timeframe": tf, "from": frm, "to": to,
            "balance": 10000, "dataMode": "m1", "spreadPips": spread, "params": params}
    last = None
    for attempt in range(retries + 1):
        try:
            rid = api("/backtest", body)["id"]
            t0 = time.time()
            while True:
                time.sleep(8)
                r = api("/result/" + rid)
                if r["status"] == "completed":
                    return r["report"]
                if r["status"] == "failed":
                    raise RuntimeError(r.get("error", "failed"))
                if time.time() - t0 > timeout_s:
                    raise RuntimeError("timeout")
        except Exception as e:
            last = e
            if attempt < retries:
                time.sleep(5)  # transient (np. HTTP 404 na 1. wywolaniu) -> retry
                continue
            raise last


def bucket(report):
    """history.items -> (by_month{'RRRR-MM':net}, net_total, n, trades).
    trades = [[closeTime_ms, net], ...] — do policzenia miesiecznego max DD
    portfela w rendererze (DD nie jest addytywne, wiec trzymamy transakcje)."""
    items = ((report.get("history") or {}).get("items")) or []
    bm = {}
    total = 0.0
    trades = []
    for it in items:
        net, ct = it.get("net"), it.get("closeTime")
        if net is None or ct is None:
            continue
        dt = datetime.fromtimestamp(ct / 1000.0, tz=timezone.utc)
        mk = f"{dt.year:04d}-{dt.month:02d}"
        bm[mk] = round(bm.get(mk, 0.0) + net, 2)
        total += net
        trades.append([int(ct), round(float(net), 2)])
    return bm, round(total, 2), len(items), trades


def main():
    force = "--force" in sys.argv
    out = {}
    if os.path.exists(OUT) and not force:
        with open(OUT, encoding="utf-8") as f:
            out = json.load(f)

    for tag, name, robot, sym, tf, spread, params in STREAMS:
        rec = out.get(tag) if not force else None
        if not rec or "by_month" not in rec:
            rec = {"name": name, "robot": robot, "symbol": sym, "tf": tf,
                   "spread": spread, "by_month": {}, "by_year": {}, "n": 0,
                   "segs": {}}
        print(f"\n===== {tag} ({robot} {sym} {tf}) =====", flush=True)
        for yr, frm, to in SEGS:
            if rec["segs"].get(yr) and not rec["segs"][yr].get("error") and not force:
                print(f"  {yr}: [skip] juz policzony", flush=True)
                continue
            try:
                rep = run_seg(robot, sym, tf, spread, params, frm, to)
                bm, net, n, trades = bucket(rep)
                roi = (rep.get("main") or {}).get("roi")
                # wczep miesiace tego segmentu do laczonej mapy (nadpisz per-miesiac)
                for k, v in bm.items():
                    rec["by_month"][k] = v
                rec["by_year"][yr[:4] if yr != "2026H1" else "2026"] = net
                rec["n"] += n
                rec["segs"][yr] = {"net": net, "n": n, "roi": roi, "trades": trades}
                print(f"  {yr}: ROI {roi}%  net {net}  n {n}", flush=True)
            except Exception as e:
                rec["segs"][yr] = {"error": str(e)}
                print(f"  {yr}: ERROR {e}", flush=True)
            out[tag] = rec
            with open(OUT, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=1)

    print("\nZAPISANO " + OUT, flush=True)


if __name__ == "__main__":
    sys.exit(main())
