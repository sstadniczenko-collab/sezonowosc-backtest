# -*- coding: utf-8 -*-
"""TEST FUNDAMENTU REŻIMU: czy trend/chop (efficiency ratio) tłumaczy, kiedy
momentum-boty vs mean-reversion-boty zarabiają? Na złocie, NQ, DAX.

ER (Kaufman) per miesiąc = |close_last-close_first| / suma|dziennych zmian|.
1 = czysty trend, ~0 = chop. Hipoteza:
  momentum (gold+DAX): corr(P&L, ER) > 0   (lubią trend)
  mean-rev (NQ):       corr(P&L, ER) < 0    (lubią chop)
Jeśli znaki się zgadzają -> reżim ma REALNY fundament i flip 2024→2026 się tłumaczy.
Dane: yfinance (cena) + monthly_bt_results.json (P&L botów). Bez nowych backtestów.
"""
import json
import os
import sys
import warnings

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")
for s in (sys.stdout, sys.stderr):
    try: s.reconfigure(encoding="utf-8")
    except Exception: pass

HERE = os.path.dirname(os.path.abspath(__file__))
mbt = json.load(open(os.path.join(HERE, "data", "monthly_bt_results.json"), encoding="utf-8"))

INSTR = {"gold": "GC=F", "nq": "^NDX", "dax": "^GDAXI"}
# bot -> (instrument, typ)
BOTS = {"gdep": ("gold", "momentum"), "grt": ("gold", "momentum"), "trr": ("gold", "momentum"),
        "turtle": ("gold", "momentum"), "daxl": ("dax", "momentum"), "orb": ("dax", "momentum"),
        "olb": ("dax", "momentum"), "ppk": ("nq", "mean-rev"), "btfd": ("nq", "mean-rev"),
        "rsi": ("nq", "mean-rev")}


def monthly_er(ticker):
    raw = yf.download(ticker, start="2022-12-01", interval="1d", progress=False, auto_adjust=False)
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    c = raw.rename(columns=str.lower)["close"].dropna()
    c.index = pd.to_datetime(c.index).tz_localize(None)
    out = {}
    for (y, m), g in c.groupby([c.index.year, c.index.month]):
        if len(g) < 5:
            continue
        net = abs(g.iloc[-1] - g.iloc[0]); path = g.diff().abs().sum()
        out[f"{y:04d}-{m:02d}"] = float(net / path) if path else 0.0
    return out


def pearson(xs, ys):
    n = len(xs)
    if n < 4:
        return None, n
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs); syy = sum((y - my) ** 2 for y in ys)
    return (sxy / (sxx ** .5 * syy ** .5) if sxx and syy else None), n


er = {k: monthly_er(v) for k, v in INSTR.items()}
print("=== Efficiency Ratio (trend↑ / chop↓) — średnia per rok ===")
print("instr   2023   2024   2025  2026H1")
for k in INSTR:
    row = []
    for yr, mm in (("2023", range(1, 13)), ("2024", range(1, 13)), ("2025", range(1, 13)), ("2026H1", range(1, 8))):
        vals = [er[k][f"{yr[:4]}-{m:02d}"] for m in mm if f"{yr[:4]}-{m:02d}" in er[k]]
        row.append(f"{sum(vals)/len(vals):.2f}" if vals else "  —")
    print(f"{k:6} " + " ".join(v.rjust(6) for v in row))

print("\n=== corr(P&L bota, ER instrumentu) per bot ===")
print("bot     instr  typ         corr   n   oczekiwane   zgodne?")
agg = {"momentum": ([], []), "mean-rev": ([], [])}
for t, (ins, typ) in BOTS.items():
    if t not in mbt or "by_month" not in mbt[t]:
        continue
    bm = mbt[t]["by_month"]
    xs, ys = [], []
    for mk, pnl in bm.items():
        if mk in er[ins]:
            xs.append(er[ins][mk]); ys.append(pnl)
            agg[typ][0].append(er[ins][mk]); agg[typ][1].append(pnl)
    r, n = pearson(xs, ys)
    exp = "+" if typ == "momentum" else "−"
    ok = "✓" if (r is not None and ((r > 0.1) == (typ == "momentum")) and abs(r) > 0.1) else \
         ("~" if (r is not None and abs(r) <= 0.1) else "✗")
    print(f"{t:6}  {ins:5}  {typ:10} {('%+.2f'%r) if r is not None else '  —':>6} {n:>3}   {exp:^10}   {ok}")

print("\n=== ZBIORCZO (pula wszystkich botów danego typu) ===")
for typ in ("momentum", "mean-rev"):
    r, n = pearson(agg[typ][0], agg[typ][1])
    exp = "corr > 0 (lubią trend)" if typ == "momentum" else "corr < 0 (lubią chop)"
    verd = "?" if r is None else (
        "POTWIERDZA fundament" if ((r > 0) == (typ == "momentum")) and abs(r) > 0.12 else
        "słabo/brak" if abs(r) <= 0.12 else "PRZECIWNIE (fundament pada)")
    print(f"  {typ:10} corr {('%+.2f'%r) if r is not None else '—'}  n={n}  oczek.: {exp}  → {verd}")

print("\nWniosek: jeśli momentum corr>0 i mean-rev corr<0 -> trend/chop realnie steruje")
print("wynikami botów = mamy fundament reżimu. Sprawdź też flip ER: czy 2026 gold↑ / DAX↓.")
