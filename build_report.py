# -*- coding: utf-8 -*-
"""Sezonowość — backtest: samodzielny raport HTML (osobny od vtrade-stats).

Czyta:
  data/monthly_bt_results.json  (silnik monthly_bt.py; fallback: ../hts_loop/)
  data/lw_seasonal.json         (Larry Williams 2026 — lw_parse.py)
  data/cot_seasonal.json        (CFTC COT — cot_fetch.py)
Pisze: index.html (dark, samodzielny — otwórz w przeglądarce).

Układ: OŚ CZASU pozioma (miesiące od lewej do prawej przez wszystkie lata,
suwak poziomy), portfel + każdy bot w tej samej osi; % zysku/straty per bot;
podsumowanie każdego roku; osobno odcisk sezonowy (Śr/miesiąc) + nakładki COT/LW.
"""
import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
MONTHS_PL = ['Sty', 'Lut', 'Mar', 'Kwi', 'Maj', 'Cze', 'Lip', 'Sie', 'Wrz', 'Paź', 'Lis', 'Gru']
BASE = 10000.0

for s in (sys.stdout, sys.stderr):
    try: s.reconfigure(encoding="utf-8")
    except Exception: pass


def load(name, *fallback_dirs):
    for d in (DATA, *fallback_dirs):
        p = os.path.join(d, name)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                return json.load(f)
    return None


def _axis(keys):
    """Ciągła oś RRRR-MM od min do max (z lukami wypełnionymi)."""
    y0, m0 = int(keys[0][:4]), int(keys[0][5:7])
    y1, m1 = int(keys[-1][:4]), int(keys[-1][5:7])
    out = []
    cy, cm = y0, m0
    while (cy, cm) <= (y1, m1):
        out.append(f'{cy:04d}-{cm:02d}')
        cm += 1
        if cm > 12:
            cm = 1; cy += 1
    return out


def _mcell(v, scale, dd=None, mnew=False):
    cls = 'm ynew' if mnew else 'm'
    if abs(v) < 0.005 and not dd:
        return f'<td class="{cls} z" title="brak transakcji">·</td>'
    a = 0.12 + 0.78 * min(1.0, abs(v) / scale) if scale else 0.5
    rgb = '38,166,154' if v > 0 else ('239,83,80' if v < 0 else '120,123,134')
    dd_html = f'<div class="dd">▼{dd:.0f}</div>' if dd and dd >= 0.5 else ''
    return f'<td class="{cls} hc" style="background:rgba({rgb},{a:.2f})"><div class="v">{v:+.0f}</div>{dd_html}</td>'


def _num(v, pct=False, bold=True, dim=False):
    col = '#787b86' if dim else ('#26a69a' if v > 0 else ('#ef5350' if v < 0 else '#787b86'))
    s = f'{v:+.0f}%' if pct else f'{v:+.0f}'
    return f'<td class="num" style="color:{col};font-weight:{700 if bold else 400}">{s}</td>'


def render_section(monthly_bt, lw, cot):
    bots = {t: d for t, d in (monthly_bt or {}).items()
            if isinstance(d, dict) and d.get('by_month') and not d.get('error')}
    errs = {t: d for t, d in (monthly_bt or {}).items() if isinstance(d, dict) and d.get('error')}
    if not bots:
        return ('<div class="note">Brak policzonych strumieni — backtest jeszcze się liczy '
                '(monthly_bt.py). Odśwież po zakończeniu.</div>')

    keys = sorted({k for d in bots.values() for k in d['by_month']})
    axis = _axis(keys)
    years = sorted({mk[:4] for mk in axis})

    # portfel: net + DD (z połączonych transakcji) per miesiąc
    port = {mk: 0.0 for mk in axis}
    for d in bots.values():
        for k, v in d['by_month'].items():
            if k in port:
                port[k] += v
    month_tr = {}
    for d in bots.values():
        for seg in (d.get('segs') or {}).values():
            for tr in (seg.get('trades') or []):
                dt = datetime.fromtimestamp(tr[0] / 1000.0, tz=timezone.utc)
                month_tr.setdefault(f'{dt.year:04d}-{dt.month:02d}', []).append((tr[0], tr[1]))
    dd = {}
    for mk, lst in month_tr.items():
        lst.sort()
        cum = peak = d0 = 0.0
        for _, n in lst:
            cum += n; peak = max(peak, cum); d0 = max(d0, peak - cum)
        dd[mk] = round(d0, 2)

    # kolejność botów wg wkładu
    order = sorted(bots.items(), key=lambda kv: -sum(kv[1].get('by_year', {}).values()))

    # ── OŚ CZASU (pozioma, przewijalna) ──
    yr_cnt = {y: sum(1 for mk in axis if mk[:4] == y) for y in years}
    yr_net = {y: sum(port[mk] for mk in axis if mk[:4] == y) for y in years}
    h1 = ['<tr class="hd"><th class="stick l" rowspan="2">Strumień</th>']
    for y in years:
        col = '#26a69a' if yr_net[y] > 0 else '#ef5350'
        h1.append(f'<th colspan="{yr_cnt[y]}" class="ynew ygrp">{y} · '
                  f'<span style="color:{col}">{yr_net[y]:+.0f}€</span></th>')
    h1.append('<th rowspan="2">Razem €</th><th rowspan="2">%</th></tr>')
    h2 = ['<tr class="hd">']
    for mk in axis:
        m = int(mk[5:7])
        h2.append(f'<th class="m{" ynew" if m == 1 else ""}">{MONTHS_PL[m-1]}</th>')
    h2.append('</tr>')

    # portfel row
    pscale = max((abs(port[mk]) for mk in axis), default=1.0) or 1.0
    prow = ['<tr class="port"><td class="stick l b">📊 Portfel (Σ)</td>']
    for mk in axis:
        prow.append(_mcell(port[mk], pscale, dd.get(mk), int(mk[5:7]) == 1))
    ptot = sum(port.values())
    prow.append(_num(ptot) + _num(ptot / (len(bots) * BASE) * 100, pct=True))
    prow.append('</tr>')

    # bot rows
    brows = []
    for t, d in order:
        bm = d['by_month']
        sc = max((abs(bm.get(mk, 0.0)) for mk in axis), default=1.0) or 1.0
        r = [f'<td class="stick l">{d.get("name", t)} <span class="dim">{d.get("symbol","")} {d.get("tf","")}</span></td>']
        for mk in axis:
            r.append(_mcell(bm.get(mk, 0.0), sc, None, int(mk[5:7]) == 1))
        tot = sum(d.get('by_year', {}).values())
        r.append(_num(tot) + _num(tot / BASE * 100, pct=True))
        brows.append('<tr>' + ''.join(r) + '</tr>')
    for t, d in errs.items():
        brows.append(f'<tr class="err"><td class="stick l">{d.get("name", t)}</td>'
                     f'<td colspan="{len(axis)+2}" style="color:#ef5350">błąd: {d.get("error")}</td></tr>')

    timeline = ('<div class="scroll"><table class="grid tl"><thead>' + ''.join(h1) + ''.join(h2)
                + '</thead><tbody>' + ''.join(prow) + ''.join(brows) + '</tbody></table></div>')

    # ── PODSUMOWANIE LAT ──
    ys_rows = []
    for y in years:
        act = [d for _, d in bots.items() if any(k[:4] == y for k in d['by_month'])]
        pcts = [sum(v for k, v in d['by_month'].items() if k[:4] == y) / BASE * 100 for d in act]
        avg = sum(pcts) / len(pcts) if pcts else 0.0
        ntr = sum(len(month_tr.get(mk, [])) for mk in axis if mk[:4] == y)
        ys_rows.append(f'<tr><td class="l b">{y}</td>' + _num(yr_net[y])
                       + _num(avg, pct=True) + f'<td class="num dim">{len(act)}</td>'
                       + f'<td class="num dim">{ntr}</td></tr>')
    year_tbl = ('<div class="h2">Podsumowanie roczne (portfel; % = średni zwrot na bota, baza 10k)</div>'
                '<div class="scroll"><table class="grid"><thead><tr class="hd"><th class="l">Rok</th>'
                '<th>Σ € portfel</th><th>śr %/bota</th><th>botów</th><th>transakcji</th></tr></thead>'
                '<tbody>' + ''.join(ys_rows) + '</tbody></table></div>')

    # ── ODCISK SEZONOWY (12 mies.) + NAKŁADKI COT/LW ──
    col_sum = {m: sum(port[mk] for mk in axis if int(mk[5:7]) == m) for m in range(1, 13)}
    yrs_with = {m: len({mk[:4] for mk in axis if int(mk[5:7]) == m}) for m in range(1, 13)}
    col_avg = {m: (col_sum[m] / yrs_with[m]) if yrs_with[m] else 0.0 for m in range(1, 13)}
    sa = max((abs(col_avg[m]) for m in range(1, 13)), default=1.0) or 1.0

    def acell(v):
        if abs(v) < 0.005:
            return '<td class="m z">·</td>'
        a = 0.12 + 0.78 * min(1.0, abs(v) / sa)
        rgb = '38,166,154' if v > 0 else '239,83,80'
        return f'<td class="m hc b" style="background:rgba({rgb},{a:.2f})">{v:+.0f}</td>'

    def sgcell(s, title=''):
        mp = {'long': ('▲', '#26a69a'), 'short': ('▼', '#ef5350'),
              'caution': ('~', '#e8c766'), 'neutral': ('•', '#787b86')}
        if not s:
            return '<td class="m z" style="text-align:center">–</td>'
        ch, col = mp.get(s, ('?', '#787b86'))
        tt = f' title="{title}"' if title else ''
        return f'<td class="m" style="text-align:center;color:{col};font-weight:700"{tt}>{ch}</td>'

    def ov_row(label, sig, source, titles=None):
        cells = ''.join(sgcell(sig[m] if m < len(sig) else None,
                               (titles[m] if titles and m < len(titles) else '')) for m in range(12))
        return f'<tr><td class="stick l ov">{label}</td>{cells}<td class="src">{source}</td></tr>'

    sh = '<tr class="hd"><th class="stick l">Miesiąc kalendarzowy</th>' + ''.join(
        f'<th class="m">{MONTHS_PL[m]}</th>' for m in range(12)) + '<th>—</th></tr>'
    seas = [f'<tr class="port"><td class="stick l b" style="color:#e8c766">Śr / miesiąc (nasz odcisk)</td>'
            + ''.join(acell(col_avg[m]) for m in range(1, 13)) + '<td class="src">backtest</td></tr>']
    if lw or cot:
        groups = [('🥇 Złoto — DEP/RT/Azja/Turtle', 'gold', 'gold'),
                  ('📈 US indeksy — PPK/BTFD/RSI + DAX', 'sp_djia', 'nasdaq'),
                  ('💴 JPY — Adaptacja', 'usd', 'jpy')]
        for title, lwk, cotk in groups:
            seas.append(f'<tr><td colspan="14" class="grp">{title}</td></tr>')
            la = (lw or {}).get('assets', {}).get(lwk)
            if la:
                seas.append(ov_row('LW · ' + la['label'], la['sig'], 'Larry Williams 2026'))
            cm = (cot or {}).get('markets', {}).get(cotk)
            if cm and not cm.get('error'):
                titles = [(f"% lat na plus: {cm['pct_up'][m]}%, śr Δ {cm['mean_chg'][m]} kontr."
                           if cm.get('pct_up') and cm['pct_up'][m] is not None else 'brak') for m in range(12)]
                seas.append(ov_row('COT · ' + cm['label'], cm['sig'], f"CFTC {cm.get('span','')}", titles))
    seasonal = ('<div class="h2">Odcisk sezonowy (miesiąc kalendarzowy) vs nakładki referencyjne '
                '— ▲ long · ▼ short · ~ ostrożność · • neutralnie</div>'
                '<div class="scroll"><table class="grid"><thead>' + sh + '</thead><tbody>'
                + ''.join(seas) + '</tbody></table></div>')

    n_ok, n_all = len(bots), len(bots) + len(errs)
    banner = (f'<div class="banner">🗓️ Backtest championów, oś czasu {axis[0]}…{axis[-1]} ({n_ok}/{n_all} botów). '
              'Każdy bot na bazie 10 000 €, ryzyko wg USTAWIENIA_FORWARD. '
              'W komórce Portfela: net € + <b style="color:#ffb3ab">▼max DD</b> konta w tym miesiącu.</div>'
              '<div class="note">Kolory intensywność ∝ wielkość <b>w obrębie wiersza</b> (każdy bot skalowany '
              'do siebie — widać jego własny rytm). <b>·</b> = brak transakcji. Miesiące <b>sprzed 2023 '
              'niedostępne</b> (dane brokera m1 od ~2023) → oś to ~3,5 roku = cross-check, nie twardy wzorzec; '
              'głębszą historię dają nakładki <b>COT</b>/<b>LW</b> niżej. Przewiń oś w bok (suwak).</div>')
    return banner + timeline + year_tbl + seasonal


PAGE = """<!doctype html><html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sezonowość — backtest</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;background:#131722;color:#d1d4dc;font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif}}
.wrap{{max-width:1600px;margin:0 auto;padding:24px 16px 60px}}
h1{{font-size:22px;margin:0 0 2px;color:#e8eaed}}
.sub{{color:#787b86;font-size:12.5px;margin-bottom:18px}}
.banner{{margin:8px 0 6px;padding:10px 14px;background:#2a2e39;border-left:3px solid #e8c766;
  color:#c9cdd6;font-size:12.5px;font-weight:600;border-radius:0 4px 4px 0}}
.note{{margin:6px 0 10px;padding:10px 14px;background:#1e222d;border:1px solid #2a2e39;border-radius:6px;
  color:#9aa0ad;font-size:11.5px;line-height:1.65}}
.h2{{margin:24px 0 6px;color:#9aa0ad;font-size:12px;font-weight:600}}
.scroll{{overflow-x:auto;border:1px solid #2a2e39;border-radius:6px}}
table.grid{{border-collapse:collapse;font-size:12px;color:#c9cdd6;white-space:nowrap}}
table.tl{{min-width:100%}}
.grid th{{padding:5px 6px;text-align:right;background:#2a2e39;color:#9aa0ad;font-weight:600}}
.grid th.l,.grid td.l{{text-align:left}}
.grid td{{padding:3px 6px;text-align:right;font-variant-numeric:tabular-nums}}
.grid td.l{{color:#d1d4dc}}
.grid td.m,.grid th.m{{padding:3px 5px;min-width:34px;text-align:right}}
.grid th.m{{text-align:right}}
.grid td.z{{color:#3d414b}}
.grid td.hc{{color:#f0f2f4}}
.grid td.hc .v{{font-weight:600}}
.grid td.hc.b{{font-weight:700}}
.grid td.hc .dd{{color:#ffb3ab;font-size:8.5px;margin-top:1px}}
.grid td.num{{padding:3px 9px;min-width:64px}}
.grid tr.port td{{border-top:2px solid #3a3e49;border-bottom:1px solid #3a3e49}}
.grid .ynew{{border-left:2px solid #3a3e49}}
.grid th.ygrp{{text-align:center;color:#c9cdd6}}
.grid td.stick,.grid th.stick{{position:sticky;left:0;z-index:2;min-width:150px}}
.grid td.stick{{background:#131722}}
.grid th.stick{{background:#2a2e39}}
.grid td.ov{{color:#c9cdd6;font-size:11.5px}}
.grid td.src{{color:#787b86;font-size:10px;text-align:right}}
.grid td.grp{{padding:6px 10px 1px;color:#9aa0ad;font-size:11px}}
.grid .dim{{color:#787b86;font-size:11px}}
.grid tr.err{{opacity:.6}}
.foot{{margin-top:22px;color:#5c606b;font-size:11px;line-height:1.6;border-top:1px solid #2a2e39;padding-top:12px}}
</style></head><body><div class="wrap">
<h1>Sezonowość — backtest</h1>
<div class="sub">{sub}</div>
{section}
<div class="foot">Źródła nakładek: {lwsrc} · {cotsrc}<br>
Wygenerowano {ts} · osobny projekt od vtrade-stats (statystyki live ≠ backtest).</div>
</div></body></html>"""


def main():
    mbt = load("monthly_bt_results.json", os.path.join(os.path.dirname(HERE), "hts_loop"))
    lw = load("lw_seasonal.json")
    cot = load("cot_seasonal.json")
    section = render_section(mbt, lw, cot)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    nb = len([1 for d in (mbt or {}).values() if isinstance(d, dict) and d.get("by_month") and not d.get("error")])
    sub = (f"Oś czasu miesięcznego P&amp;L portfela {nb} botów (backtest championów) vs cykle COT / "
           "Larry Williams. Model: 1 bot = 1 konto 10k. Przewiń oś w bok →")
    html = PAGE.format(sub=sub, section=section, ts=ts,
                       lwsrc=(lw or {}).get("source", "LW —"),
                       cotsrc=(cot or {}).get("source", "COT —"))
    out = os.path.join(HERE, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("OK ->", out, f"| {nb} botów, {len(html)} B")


if __name__ == "__main__":
    main()
