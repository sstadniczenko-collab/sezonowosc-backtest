# -*- coding: utf-8 -*-
"""Rzeczywistość 2026 per aktywo: realne ruchy TYGODNIOWE (yfinance) dla tygodni,
które już były + sezonowy wzorzec CENOWY (historyczny) na tygodnie przyszłe =
'predykcja'. Do porównania z LW i COT (jak sezonowość ma się do rzeczywistości).

Wynik: data/reality_2026.json  -> {key: {"weekly": {"YYYY-MM-DD": +1/-1}, "monthly": [12 znaków long/short/neutral], "invert": bool}}
weekly kluczowane datą PONIEDZIAŁKU (jak oś tygodniowa w raporcie).
"""
import json
import os
import sys
import warnings
from datetime import date, timedelta

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")
for s in (sys.stdout, sys.stderr):
    try: s.reconfigure(encoding="utf-8")
    except Exception: pass

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "reality_2026.json")

# key, yfinance ticker, invert? (dla jena: rzeczywistość jena = odwrotność USDJPY)
ASSETS = [
    ("gold", "GC=F", False), ("spx", "^GSPC", False), ("ndx", "^NDX", False),
    ("usd", "DX-Y.NYB", False), ("oil", "CL=F", False), ("bonds", "TLT", False),
    ("btc", "BTC-USD", False), ("reits", "VNQ", False), ("silver", "SI=F", False),
    ("platinum", "PL=F", False), ("palladium", "PA=F", False), ("copper", "HG=F", False),
    ("nikkei", "^N225", False), ("jpy", "JPY=X", True), ("eur", "EURUSD=X", False),
    ("gbp", "GBPUSD=X", False), ("aud", "AUDUSD=X", False), ("cocoa", "CC=F", False),
    ("coffee", "KC=F", False),
]

# 52 poniedziałki 2026 (jak w raporcie)
d = date(2026, 1, 1)
while d.weekday() != 0:
    d += timedelta(days=1)
WEEKS = [d + timedelta(days=7 * i) for i in range(52)]
TODAY = date(2026, 8, 1)


def norm(raw):
    if raw is None or len(raw) == 0:
        return pd.DataFrame()
    if isinstance(raw.columns, pd.MultiIndex):
        raw = raw.copy(); raw.columns = raw.columns.get_level_values(0)
    raw = raw.rename(columns=str.lower)
    if "close" not in raw.columns:
        return pd.DataFrame()
    df = raw[["close"]].dropna()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df.sort_index()


def sgn(x, inv):
    x = -x if inv else x
    return "long" if x > 0 else ("short" if x < 0 else "neutral")


def one(ticker, inv):
    daily = norm(yf.download(ticker, period="max", interval="1d", progress=False, auto_adjust=False))
    if daily.empty:
        return None
    c = daily["close"]
    # --- tygodnie realne 2026 ---
    weekly = {}
    for m in WEEKS:
        if m >= TODAY:
            continue  # przyszłość -> predykcja z monthly
        prior = c[c.index < pd.Timestamp(m)]
        wk = c[(c.index >= pd.Timestamp(m)) & (c.index < pd.Timestamp(m + timedelta(days=7)))]
        if len(prior) == 0 or len(wk) == 0:
            continue
        ret = wk.iloc[-1] / prior.iloc[-1] - 1.0
        weekly[m.isoformat()] = sgn(ret, inv)
    # --- sezonowy wzorzec miesięczny (cała historia) ---
    mret = c.resample("ME").last().pct_change().dropna()
    monthly = []
    for mo in range(1, 13):
        vals = mret[mret.index.month == mo]
        monthly.append(sgn(vals.mean(), inv) if len(vals) else "neutral")
    return {"weekly": weekly, "monthly": monthly, "invert": inv, "ticker": ticker,
            "hist_from": str(c.index[0].date()), "n_weeks_real": len(weekly)}


def main():
    out = {}
    for key, tk, inv in ASSETS:
        try:
            r = one(tk, inv)
            if r:
                out[key] = r
                print(f"{key:9} {tk:10} realnych tyg: {r['n_weeks_real']}, hist od {r['hist_from']}", flush=True)
            else:
                print(f"{key:9} {tk:10} BRAK danych", flush=True)
        except Exception as e:
            print(f"{key:9} {tk:10} ERROR {e}", flush=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\nOK ->", OUT)


if __name__ == "__main__":
    main()
