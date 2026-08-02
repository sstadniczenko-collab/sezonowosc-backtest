# -*- coding: utf-8 -*-
"""WALK-FORWARD: czy backtest jednego okresu PRZEWIDUJE następny?
Test hipotezy usera: backtest 2024→2025, 2024+2025→2026H1 itd.
Dane: monthly_bt_results.json (ROI per rok + P&L miesięczny per bot). Bez nowych
backtestów. Jeśli korelacja rok→rok wysoka -> backtestowi można ufać (ranking
trzyma się). Jeśli niska -> wynik zależy od reżimu, live-rozjazd jest NORMALNY,
a plan sezonowy (OFF-miesiące) przeuczony.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for s in (sys.stdout, sys.stderr):
    try: s.reconfigure(encoding="utf-8")
    except Exception: pass

mbt = json.load(open(os.path.join(HERE, "data", "monthly_bt_results.json"), encoding="utf-8"))
bots = {t: v for t, v in mbt.items() if isinstance(v, dict) and v.get("segs")}
YEARS = ["2023", "2024", "2025", "2026H1"]


def roi(t, y):
    s = bots[t].get("segs", {}).get(y, {})
    return None if s.get("error") or "roi" not in s else s["roi"]


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs); syy = sum((y - my) ** 2 for y in ys)
    return sxy / (sxx ** .5 * syy ** .5) if sxx and syy else None


def spearman(xs, ys):
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0] * len(v)
        for pos, i in enumerate(order):
            r[i] = pos
        return r
    return pearson(rank(xs), rank(ys))


print("=== ROI% per rok per bot (backtest) ===")
print("bot".ljust(8) + "".join(y.rjust(9) for y in YEARS))
for t in bots:
    print(t.ljust(8) + "".join((f"{roi(t,y):+.1f}" if roi(t, y) is not None else "  —").rjust(9) for y in YEARS))

print("\n=== KORELACJA rok→rok (czy backtest przewiduje następny okres?) ===")
pairs = [("2024", "2025"), ("2023", "2024"), ("2025", "2026H1"), ("2024", "2026H1")]
for a, b in pairs:
    xs, ys = [], []
    for t in bots:
        ra, rb = roi(t, a), roi(t, b)
        if ra is not None and rb is not None:
            xs.append(ra); ys.append(rb)
    p, s = pearson(xs, ys), spearman(xs, ys)
    verd = ("SILNA (backtest przewiduje)" if (s or 0) > 0.5 else
            "słaba/żadna (reżim rządzi)" if abs(s or 0) < 0.3 else "umiarkowana")
    print(f"  {a:6}→{b:6}  n={len(xs):2}  Pearson {p:+.2f}  Spearman(rank) {s:+.2f}  → {verd}"
          if p is not None else f"  {a}→{b}: za mało par")

# 2024+2025 średnia -> 2026H1
xs, ys = [], []
for t in bots:
    r24, r25, r26 = roi(t, "2024"), roi(t, "2025"), roi(t, "2026H1")
    if None not in (r24, r25, r26):
        xs.append((r24 + r25) / 2); ys.append(r26)
p, s = pearson(xs, ys), spearman(xs, ys)
print(f"  (2024+2025)/2 →2026H1  n={len(xs)}  Pearson {p:+.2f}  Spearman {s:+.2f}")

print("\n=== PERSYSTENCJA MIESIĘCY (czy 'słabe miesiące' się powtarzają rok do roku?) ===")
# dla każdego (bot,miesiąc): znak P&L w 2024 vs 2025; ile % się zgadza
agree = tot = 0
for t in bots:
    bm = bots[t]["by_month"]
    for m in range(1, 13):
        a = bm.get(f"2024-{m:02d}"); b = bm.get(f"2025-{m:02d}")
        if a is None or b is None:
            continue
        tot += 1
        if (a > 0) == (b > 0):
            agree += 1
print(f"  znak miesiąca 2024==2025: {agree}/{tot} = {100*agree/tot:.0f}%  "
      f"(50% = losowo → sezonowość NIE persystuje; >65% = realny wzorzec)")
