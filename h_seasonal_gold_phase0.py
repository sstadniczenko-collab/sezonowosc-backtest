# -*- coding: utf-8 -*-
"""PHASE-0 (pętla): czy sezonowe claimy LW na ZŁOCIE replikują się w danych?
NIE bot — tani replay python + kontrola permutacyjna, zanim cokolwiek kodujemy.

Testuje 3 pre-zarejestrowane claimy LW (gold):
  C1  Bias końca tygodnia: czw/pt mają dodatni dzienny zwrot (LW: "buy Thu/Fri").
  C2  Rajd sezonowy sty–maj: te miesiące silniejsze niż reszta (LW: 90%/47lat).
  C3  TDOM-1: 1. dzień handlowy miesiąca ma dodatni zwrot (LW: >$89k).

Kontrola: permutacja etykiet (dzień tyg. / miesiąc) N razy -> p = odsetek losowań
z efektem >= obserwowany. Dane: yfinance GC=F (max, ~2000+). Zwrot = open->close
dnia (proxy 'buy open, out same day') dla C1/C3; miesięczny close->close dla C2.
"""
import random
import sys
import warnings

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")
for s in (sys.stdout, sys.stderr):
    try: s.reconfigure(encoding="utf-8")
    except Exception: pass
random.seed(42); np.random.seed(42)

raw = yf.download("GC=F", period="max", interval="1d", progress=False, auto_adjust=False)
if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.get_level_values(0)
df = raw.rename(columns=str.lower)[["open", "high", "low", "close"]].dropna().sort_index()
df["dow"] = df.index.dayofweek            # 0=pon..4=pt
df["mon"] = df.index.month
df["oc"] = (df["close"] / df["open"] - 1.0) * 100.0   # open->close %
print(f"GC=F: {len(df)} dni, {df.index[0].date()}..{df.index[-1].date()}\n")


def perm_p(values, labels, mask_fn, n=2000):
    """p = P(losowy podzbiór o tej samej liczności ma średnią >= obserwowaną)."""
    obs_mask = mask_fn(labels)
    obs = values[obs_mask].mean()
    k = int(obs_mask.sum())
    ge = 0
    v = values.to_numpy()
    idx = np.arange(len(v))
    for _ in range(n):
        pick = np.random.choice(idx, k, replace=False)
        if v[pick].mean() >= obs:
            ge += 1
    return obs, k, ge / n


# C1 — czw/pt (dow 3,4) dodatni open->close
obs, k, p = perm_p(df["oc"], df["dow"], lambda L: L.isin([3, 4]).to_numpy())
base = df["oc"].mean()
print(f"C1 koniec tyg (czw+pt): śr O→C {obs:+.3f}% vs cała próba {base:+.3f}%  "
      f"(n={k}, WR {100*(df['oc'][df['dow'].isin([3,4])]>0).mean():.0f}%)  p={p:.3f}")
for d, nm in [(3, "czw"), (4, "pt")]:
    s = df["oc"][df["dow"] == d]
    print(f"     {nm}: śr {s.mean():+.3f}%  WR {100*(s>0).mean():.0f}%  n={len(s)}")

# C2 — sty–maj (mon 1..5) miesięczny zwrot silniejszy
mret = df["close"].resample("ME").last().pct_change().dropna() * 100.0
mmon = mret.index.month
obs2, k2, p2 = perm_p(mret, pd.Series(mmon, index=mret.index),
                      lambda L: L.isin([1, 2, 3, 4, 5]).to_numpy())
print(f"\nC2 rajd sty–maj: śr mies. zwrot {obs2:+.2f}% vs wszystkie {mret.mean():+.2f}%  "
      f"(n={k2}, WR {100*(mret[mmon.isin([1,2,3,4,5])]>0).mean():.0f}%)  p={p2:.3f}")
by = mret.groupby(mmon).mean()
print("     śr/miesiąc: " + " ".join(f"{m}:{by.get(m,0):+.1f}" for m in range(1, 13)))

# C3 — TDOM-1 (pierwszy dzień handlowy miesiąca) open->close
first = df.groupby([df.index.year, df.index.month]).head(1)
print(f"\nC3 TDOM-1: śr O→C {first['oc'].mean():+.3f}% vs cała próba {base:+.3f}%  "
      f"(n={len(first)}, WR {100*(first['oc']>0).mean():.0f}%)")
# permutacja: losowe dni vs pierwsze-dni
v = df["oc"].to_numpy(); k3 = len(first); ge = 0
for _ in range(2000):
    if v[np.random.choice(len(v), k3, replace=False)].mean() >= first["oc"].mean():
        ge += 1
print(f"     p={ge/2000:.3f}")

print("\nWNIOSEK: p<0.05 = efekt istotny vs losowość. To phase-0 — jeśli przejdzie,"
      "\nnastępny krok: pełny replay z kosztami + block bootstrap + wariant wejścia/wyjścia,"
      "\npotem walidacja cTrader (jak każdy strumień pętli).")
