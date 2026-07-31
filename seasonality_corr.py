# -*- coding: utf-8 -*-
"""Zgodność naszych botów z sezonowością LW / COT (dowód pod decyzję o filtrze/bocie).

Dla każdej klasy aktywów (złoto / US indeksy / JPY) zestawia miesięczny P&L
naszych botów z biasem LW i COT dla danego miesiąca kalendarzowego i liczy:
  - korelację (Pearson) znaku sezonowego (+1 long / 0 / -1 short) z naszym P&L,
  - średni P&L w miesiącach LW-long vs LW-short/caution (edge €),
  - win-rate w miesiącach long vs pozostałych.
Wynik: data/corr.json (+ tabela na stdout). Wstępny gdy backtest niekompletny.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
for s in (sys.stdout, sys.stderr):
    try: s.reconfigure(encoding="utf-8")
    except Exception: pass

# klasa -> (etykieta, [tagi botów], klucz LW, klucz COT)
CLASSES = [
    ("gold", "Złoto", ["gdep", "grt", "trr", "turtle"], "gold", "gold"),
    ("us",   "US indeksy (+DAX)", ["ppk", "btfd", "rsi", "daxl", "orb", "olb"], "sp_djia", "nasdaq"),
    ("jpy",  "JPY", ["jpy"], "usd", "jpy"),
]
SIGN = {"long": 1, "short": -1, "caution": 0, "neutral": 0, None: 0}


def load(name, *fb):
    for d in (DATA, *fb):
        p = os.path.join(d, name)
        if os.path.exists(p):
            return json.load(open(p, encoding="utf-8"))
    return None


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    return sxy / (sxx ** 0.5 * syy ** 0.5)


def analyze(mbt, lw, cot):
    bots = {t: d for t, d in (mbt or {}).items()
            if isinstance(d, dict) and d.get("by_month") and not d.get("error")}
    out = {}
    for key, label, tags, lwk, cotk in CLASSES:
        members = [bots[t] for t in tags if t in bots]
        if not members:
            continue
        # miesięczny P&L klasy: {'YYYY-MM': suma}
        pnl = {}
        for d in members:
            for mk, v in d["by_month"].items():
                pnl[mk] = pnl.get(mk, 0.0) + v
        if not pnl:
            continue
        months = sorted(pnl)
        lw_sig = (lw or {}).get("assets", {}).get(lwk, {}).get("sig")
        cot_m = (cot or {}).get("markets", {}).get(cotk, {})
        cot_sig = cot_m.get("sig") if not cot_m.get("error") else None

        def block(sig):
            if not sig:
                return None
            xs, ys = [], []
            long_p, other_p = [], []
            for mk in months:
                m = int(mk[5:7]) - 1
                s = SIGN.get(sig[m] if m < len(sig) else None, 0)
                xs.append(s); ys.append(pnl[mk])
                (long_p if s > 0 else other_p).append(pnl[mk])
            r = pearson(xs, ys)
            def avg(a): return round(sum(a) / len(a), 1) if a else None
            def wr(a): return round(100 * sum(1 for x in a if x > 0) / len(a)) if a else None
            edge = (avg(long_p) - avg(other_p)) if (long_p and other_p) else None
            return {"corr": round(r, 2) if r is not None else None,
                    "avg_long": avg(long_p), "avg_other": avg(other_p),
                    "edge_eur": round(edge, 1) if edge is not None else None,
                    "wr_long": wr(long_p), "wr_other": wr(other_p),
                    "n_long": len(long_p), "n_other": len(other_p)}

        out[key] = {"label": label, "n_bots": len(members), "n_months": len(months),
                    "total_pnl": round(sum(pnl.values()), 1),
                    "lw": block(lw_sig), "cot": block(cot_sig)}
    return out


def verdict(b):
    if not b or b.get("corr") is None:
        return "—"
    c, e = b["corr"], b.get("edge_eur")
    if c >= 0.15 and (e is None or e > 0):
        return "ZGODNY z cyklem"
    if c <= -0.15 and (e is None or e < 0):
        return "PRZECIW cyklowi"
    return "neutralnie / słabo"


def main():
    mbt = load("monthly_bt_results.json", os.path.join(os.path.dirname(HERE), "hts_loop"))
    lw = load("lw_seasonal.json")
    cot = load("cot_seasonal.json")
    res = analyze(mbt, lw, cot)
    json.dump(res, open(os.path.join(DATA, "corr.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("Zgodność z sezonowością (P&L klasy vs bias miesiąca):\n")
    for key, r in res.items():
        print(f"== {r['label']} ({r['n_bots']} bot., {r['n_months']} mies., Σ {r['total_pnl']}€) ==")
        for src in ("lw", "cot"):
            b = r.get(src)
            if not b:
                print(f"   {src.upper()}: brak sygnału"); continue
            print(f"   {src.upper()}: corr={b['corr']}  edge={b['edge_eur']}€/mies  "
                  f"WR long {b['wr_long']}% ({b['n_long']}) vs reszta {b['wr_other']}% ({b['n_other']})  "
                  f"→ {verdict(b)}")
        print()
    print("-> data/corr.json")


if __name__ == "__main__":
    main()
