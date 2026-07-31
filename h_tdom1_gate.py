# -*- coding: utf-8 -*-
"""BRAMKA (pętla) dla gold TDOM-1 — jedyny seasonal, który przeszedł phase-0.
Pytanie: czy edge PRZEŻYWA KOSZTY (spread złota) i block bootstrap?

Setup (proxy LW 'buy 1st trading day, exit first profitable open'):
  wejście = open 1. dnia handlowego miesiąca, wyjście = close tego dnia (open→close,
  konserwatywnie — wersja LW z 'first profitable open' byłaby korzystniejsza).
  Skip: Kwiecień, Maj (LW: skip TDOM-1 gold dla tych miesięcy).
Koszt: round-trip w % ceny (test siatki 0..0.12%). Block bootstrap (blok 6, 3000×)
→ 5. percentyl średniej netto > 0 = edge przeżywa.
"""
import sys
import warnings

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")
for s in (sys.stdout, sys.stderr):
    try: s.reconfigure(encoding="utf-8")
    except Exception: pass
np.random.seed(42)

raw = yf.download("GC=F", period="max", interval="1d", progress=False, auto_adjust=False)
if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.get_level_values(0)
df = raw.rename(columns=str.lower)[["open", "high", "low", "close"]].dropna().sort_index()

first = df.groupby([df.index.year, df.index.month]).head(1).copy()
first["mon"] = first.index.month
first = first[~first["mon"].isin([4, 5])]           # skip Kwi/Maj (LW)
first["oc"] = (first["close"] / first["open"] - 1.0) * 100.0
r = first["oc"].to_numpy()
n = len(r)
print(f"gold TDOM-1 (skip Kwi/Maj): n={n}, {first.index[0].date()}..{first.index[-1].date()}")
print(f"  brutto: śr {r.mean():+.4f}%  WR {100*(r>0).mean():.0f}%  t={r.mean()/(r.std(ddof=1)/n**0.5):.2f}\n")


def block_boot(x, cost, B=3000, bs=6):
    net = x - cost
    k = int(np.ceil(len(net) / bs))
    means = np.empty(B)
    idx0 = np.arange(len(net))
    for i in range(B):
        starts = np.random.randint(0, len(net), k)
        pick = np.concatenate([np.take(idx0, range(s, s + bs), mode="wrap") for s in starts])[:len(net)]
        means[i] = net[pick].mean()
    lo, hi = np.percentile(means, [5, 95])
    return net.mean(), lo, hi


print(f"{'koszt %':>8} | {'śr netto %':>10} | {'boot 5–95%':>18} | WR% | werdykt")
for cost in (0.0, 0.02, 0.05, 0.07, 0.10, 0.12):
    m, lo, hi = block_boot(r, cost)
    wr = 100 * ((r - cost) > 0).mean()
    verd = "PRZEŻYWA (CI>0)" if lo > 0 else ("marginalny" if m > 0 else "MARTWY")
    print(f"{cost:>8.2f} | {m:>+10.4f} | {lo:>+8.4f}..{hi:<+8.4f} | {wr:>3.0f} | {verd}")

print("\nUwaga: XAUUSD spread 20 'pipsów' w cTraderze ≈ $2 przy złocie ~$3–4k = ~0.05–0.07%.")
print("Wyjście LW 'first profitable open' jest KORZYSTNIEJSZE niż open→close (tu konserwatywnie).")
