# -*- coding: utf-8 -*-
"""Symulacja konta FTMO SWING 80k EUR na 2026 (sty–gru) z doborem parametrów
(ryzyko per bot / per miesiąc) pod limity DD FTMO.

Swing = wolno trzymać przez weekend i podczas newsów (dlatego CAŁY portfel 11
botów, nie tylko 3 jak na Normal). Limit twardy: equity nigdy ≤ 72 000 (−10% od
80k). Dzienny −5% (−4000) — proxy przez wewnątrzmiesięczne DD (dane miesięczne).

Dobór parametru (ryzyko %/bota/miesiąc) — reguła sezonowa (bez look-ahead na
2026; z profilu 2023–25 + LW):
  - miesiąc, w którym bot HISTORYCZNIE mocno tracił (worst ≤ −6% lub śr ≤ −2%) → OFF,
  - śr < 0 → redukcja do 0.20%,
  - bot LONG-only a LW dla aktywa bearish/caution → redukcja 0.20%,
  - brak historii miesiąca → ostrożnie 0.20%,
  - inaczej → baza 0.33% (zwalidowany prop-sizing, MC iter.#35).
Wynik na 2026: H1 (sty–lip) = realny backtest, H2 (sie–gru) = prognoza LW.
Skalowanie: €(10k@champ) × 8 × ryzyko/champ  → €(80k@ryzyko).
Zapis: data/ftmo_swing.json.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
for s in (sys.stdout, sys.stderr):
    try: s.reconfigure(encoding="utf-8")
    except Exception: pass

ACCOUNT = 80000.0
WALL = 0.10           # −10% twardy
BASE_R = 0.33         # bazowe ryzyko %/trade (Swing prop)
MONTHS_PL = ['Sty', 'Lut', 'Mar', 'Kwi', 'Maj', 'Cze', 'Lip', 'Sie', 'Wrz', 'Paź', 'Lis', 'Gru']

# ryzyko championa (z configów backtestu) + kierunek + klucz LW
CHAMP = {'gdep': 2.0, 'daxl': 1.0, 'grt': 1.0, 'jpy': 1.0, 'orb': 2.0, 'olb': 1.0,
         'trr': 1.0, 'ppk': 0.5, 'btfd': 1.0, 'rsi': 1.0, 'turtle': 1.0,
         'on100': 0.5, 'onger': 0.5}
LONG_ONLY = {'daxl', 'olb', 'btfd', 'on100', 'onger'}
LWMAP = {'gdep': 'gold', 'grt': 'gold', 'trr': 'gold', 'turtle': 'gold',
         'daxl': 'sp_djia', 'orb': 'sp_djia', 'olb': 'sp_djia',
         'ppk': 'sp_djia', 'btfd': 'sp_djia', 'rsi': 'sp_djia', 'jpy': 'usd',
         'on100': 'sp_djia', 'onger': 'sp_djia'}


def load(name, *fb):
    for d in (DATA, *fb):
        p = os.path.join(d, name)
        if os.path.exists(p):
            return json.load(open(p, encoding="utf-8"))
    return None


def main():
    mbt = load("monthly_bt_results.json", os.path.join(os.path.dirname(HERE), "hts_loop"))
    lw = load("lw_seasonal.json")
    cot = load("cot_seasonal.json")
    reality = load("reality_2026.json")
    lwa = (lw or {}).get("assets", {})
    cotm = (cot or {}).get("markets", {})
    rea = reality or {}
    bots = {t: d for t, d in (mbt or {}).items()
            if isinstance(d, dict) and d.get("by_month") and not d.get("error")}

    # --- konsensus RYNKU (LW+COT+cena) per aktywo/miesiąc: +1 byczo / -1 niedźwiedzio / 0 ---
    def _d(s):
        return 1 if s == "long" else (-1 if s == "short" else 0)

    def consensus(lwk, cotk, reak, m):
        ss = []
        sig = lwa.get(lwk, {}).get("sig")
        if sig:
            ss.append(sig[m - 1])
        c = cotm.get(cotk)
        if c and not c.get("error"):
            ss.append(c["sig"][m - 1])
        r = rea.get(reak)
        if r:
            ss.append(r["monthly"][m - 1])
        nz = [_d(s) for s in ss if s and _d(s) != 0]
        bull = sum(1 for x in nz if x > 0); bear = sum(1 for x in nz if x < 0)
        if bull >= 2 and bull > bear:
            return 1
        if bear >= 2 and bear > bull:
            return -1
        return 0

    # bot -> (lwkey, cotkey, reakey) aktywa, którego konsensus go napędza (tylko kierunkowe)
    TAILWIND = {'gdep': ('gold', 'gold', 'gold'), 'grt': ('gold', 'gold', 'gold'),
                'trr': ('gold', 'gold', 'gold'), 'turtle': ('gold', 'gold', 'gold'),
                'daxl': ('sp_djia', 'sp500', 'spx'), 'olb': ('sp_djia', 'sp500', 'spx'),
                'btfd': ('sp_djia', 'nasdaq', 'ndx'),
                'on100': ('sp_djia', 'nasdaq', 'ndx'), 'onger': ('sp_djia', 'sp500', 'spx')}

    def tailwind_risk(t, m):
        ak = TAILWIND.get(t)
        if not ak:
            return BASE_R                       # nie-kierunkowe (jpy/ppk/rsi/orb) = flat
        c = consensus(*ak, m)
        return 0.5 if c > 0 else (0.20 if c < 0 else BASE_R)

    # profil sezonowy 2023–25 (ROI% przy champ risk) + prognoza H2
    def hist_roi(d, m):
        return [d["by_month"][f"{Y}-{m:02d}"] / 10000 * 100
                for Y in ("2023", "2024", "2025") if f"{Y}-{m:02d}" in d["by_month"]]

    def seas_avg_eur(d, m):
        vals = [d["by_month"][f"{Y}-{m:02d}"] for Y in ("2023", "2024", "2025")
                if f"{Y}-{m:02d}" in d["by_month"]]
        return sum(vals) / len(vals) if vals else None

    def plan_risk(t, d, m):
        champ = CHAMP[t]
        roi = hist_roi(d, m)
        sig = lwa.get(LWMAP.get(t, ""), {}).get("sig")
        lwb = (sig[m - 1] if sig and m - 1 < len(sig) else None)
        if not roi:
            return 0.20, "brak historii → ostrożnie"
        avg = sum(roi) / len(roi); worst = min(roi)
        if worst <= -6 or avg <= -2:
            return 0.0, f"OFF: historycznie tracił (śr {avg:+.0f}%/worst {worst:+.0f}%)"
        if avg < 0:
            return 0.20, f"redukcja: śr {avg:+.0f}% w tym miesiącu"
        if t in LONG_ONLY and lwb in ("short", "caution"):
            return 0.20, f"redukcja: LW {lwb} a bot long-only"
        return BASE_R, ""

    def raw_eur(d, m):
        """€ (10k@champ) dla miesiąca 2026: H1 realny, H2 prognoza (seas_avg×k LW)."""
        real = d["by_month"].get(f"2026-{m:02d}")
        if real is not None:
            return real, "real"
        sa = seas_avg_eur(d, m)
        if sa is None:
            return 0.0, "brak"
        sig = lwa.get(LWMAP.get(list(bots.keys())[0], ""), {})  # placeholder, nadpisane niżej
        return sa, "pred"

    order = sorted(bots.items(), key=lambda kv: -sum(kv[1].get("by_year", {}).values()))

    def run(mode):
        """mode: 'managed' (sezonowy z profilu bota) / 'flat' / 'tailwind' (konsensus rynku LW+COT+cena)."""
        rows = []
        eq = ACCOUNT; peak = ACCOUNT; maxdd = 0.0; minq = ACCOUNT; breach = False
        for m in range(1, 13):
            perbot = {}; pnl_tot = 0.0
            for t, d in order:
                if mode == "managed":
                    r, _ = plan_risk(t, d, m)
                elif mode == "tailwind":
                    r = tailwind_risk(t, m)
                else:
                    r = BASE_R
                real = d["by_month"].get(f"2026-{m:02d}")
                if real is not None:
                    raw = real; src = "real"
                else:
                    sa = seas_avg_eur(d, m)
                    if sa is None:
                        raw = 0.0; src = "brak"
                    else:
                        sig = lwa.get(LWMAP.get(t, ""), {}).get("sig")
                        lws = ({"long": 1, "short": -1}.get(sig[m - 1], 0)) if (sig and m - 1 < len(sig)) else 0
                        ss = 1 if sa > 0 else (-1 if sa < 0 else 0)
                        k = 1.0 if (lws and lws == ss) else (0.3 if (lws and lws != ss) else 0.5)
                        raw = sa * k; src = "pred"
                scaled = raw * 8.0 * (r / CHAMP[t]) if r > 0 else 0.0
                perbot[t] = {"risk": r, "pnl": round(scaled, 0), "src": src}
                pnl_tot += scaled
            eq += pnl_tot
            peak = max(peak, eq); minq = min(minq, eq)
            dd = (peak - eq) / ACCOUNT * 100
            maxdd = max(maxdd, dd)
            if eq <= ACCOUNT * (1 - WALL):
                breach = True
            rows.append({"m": m, "label": MONTHS_PL[m - 1], "perbot": perbot,
                         "pnl": round(pnl_tot, 0), "equity": round(eq, 0),
                         "dd_pct": round(dd, 2), "dist_wall": round(eq - ACCOUNT * (1 - WALL), 0),
                         "src": "real" if m <= 7 else "pred"})
        return {"rows": rows, "end_equity": round(eq, 0), "ret_pct": round((eq - ACCOUNT) / ACCOUNT * 100, 1),
                "max_dd_pct": round(maxdd, 2), "min_equity": round(minq, 0), "breach": breach}

    # reguły per bot (dobór miesięczny)
    rules = {}
    for t, d in order:
        offm, redm = [], []
        for m in range(1, 13):
            r, why = plan_risk(t, d, m)
            if r == 0.0:
                offm.append(MONTHS_PL[m - 1])
            elif r < BASE_R:
                redm.append(MONTHS_PL[m - 1])
        rules[t] = {"name": d.get("name", t), "symbol": d.get("symbol", ""), "tf": d.get("tf", ""),
                    "champ_risk": CHAMP[t], "base_risk": BASE_R,
                    "direction": "long-only" if t in LONG_ONLY else "long/short",
                    "off_months": offm, "reduced_months": redm,
                    "ftmo_note": ("Swing: weekend/news OK. " +
                                  ("LONG-only — wrażliwy na bearish LW. " if t in LONG_ONLY else "") +
                                  ("wysokie DD historyczne — trzymać 0.33% i OFF w słabych mies." if CHAMP[t] >= 2.0 else "standard"))}

    out = {"account": ACCOUNT, "wall_pct": WALL * 100, "wall_eur": ACCOUNT * (1 - WALL),
           "base_risk": BASE_R, "type": "SWING", "n_bots": len(bots),
           "order": [t for t, _ in order],
           "bot_names": {t: d.get("name", t) for t, d in order},
           "managed": run("managed"), "flat": run("flat"), "tailwind": run("tailwind"),
           "rules": rules}
    json.dump(out, open(os.path.join(DATA, "ftmo_swing.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print("FTMO SWING 80k · 2026 (H1 real + H2 prognoza LW) — 3 warianty sizingu:")
    for k, lab in (("managed", "SEZONOWY (profil bota)"), ("flat", "FLAT 0.33 all-on"),
                   ("tailwind", "TAILWIND (konsensus LW+COT+cena)")):
        r = out[k]
        print(f"  {lab:34} koniec {r['end_equity']:.0f}€ ({r['ret_pct']:+.1f}%), "
              f"maxDD {r['max_dd_pct']:.1f}%, min {r['min_equity']:.0f}€, "
              f"ściana={'PRZEBITA' if r['breach'] else 'OK'}")
    print("-> data/ftmo_swing.json")


if __name__ == "__main__":
    main()
