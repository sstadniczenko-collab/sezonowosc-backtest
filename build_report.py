# -*- coding: utf-8 -*-
"""Sezonowość — backtest: samodzielny raport HTML (osobny od vtrade-stats).

Czyta:
  data/monthly_bt_results.json  (silnik monthly_bt.py; fallback: ../hts_loop/)
  data/lw_seasonal.json         (Larry Williams 2026 — lw_parse.py)
  data/cot_seasonal.json        (CFTC COT — cot_fetch.py)
Pisze: index.html (dark, samodzielny — otwórz w przeglądarce).

Macierz rok×miesiąc sumy P&L portfela championów + ▼max DD konta w miesiącu,
odcisk sezonowy (Śr/miesiąc) i nakładki referencyjne LW + COT do porównania
cykliczności. Uruchom: python build_report.py
"""
import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
MONTHS_PL = ['Sty', 'Lut', 'Mar', 'Kwi', 'Maj', 'Cze', 'Lip', 'Sie', 'Wrz', 'Paź', 'Lis', 'Gru']

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


def render_section(monthly_bt, lw, cot):
    bots = {t: d for t, d in (monthly_bt or {}).items()
            if isinstance(d, dict) and d.get('by_month') and not d.get('error')}
    errs = {t: d for t, d in (monthly_bt or {}).items() if isinstance(d, dict) and d.get('error')}
    if not bots:
        return ('<div class="note">Brak policzonych strumieni — backtest jeszcze się liczy '
                '(monthly_bt.py). Odśwież po zakończeniu.</div>')

    all_keys = set()
    for d in bots.values():
        all_keys.update(d['by_month'].keys())
    years = sorted({k[:4] for k in all_keys})
    port = {y: {m: 0.0 for m in range(1, 13)} for y in years}
    for d in bots.values():
        for k, v in d['by_month'].items():
            y, m = k[:4], int(k[5:7])
            if y in port:
                port[y][m] += v

    # max DD konta w miesiacu (wewnatrzmiesieczne) z polaczonych transakcji
    month_tr = {}
    for d in bots.values():
        for seg in (d.get('segs') or {}).values():
            for tr in (seg.get('trades') or []):
                dt = datetime.fromtimestamp(tr[0] / 1000.0, tz=timezone.utc)
                month_tr.setdefault(f'{dt.year:04d}-{dt.month:02d}', []).append((tr[0], tr[1]))
    dd_map = {}
    for mk, lst in month_tr.items():
        lst.sort()
        cum = peak = ddv = 0.0
        for _, n in lst:
            cum += n; peak = max(peak, cum); ddv = max(ddv, peak - cum)
        dd_map[mk] = round(ddv, 2)

    vals = [port[y][m] for y in years for m in range(1, 13)]
    scale = max((abs(x) for x in vals), default=1.0) or 1.0

    def ycell(y, m):
        v = port[y][m]
        ddv = dd_map.get(f'{y}-{m:02d}') or 0.0
        if abs(v) < 0.005 and ddv < 0.005:
            return '<td class="z" title="brak transakcji">·</td>'
        a = 0.12 + 0.78 * min(1.0, abs(v) / scale)
        rgb = '38,166,154' if v > 0 else ('239,83,80' if v < 0 else '120,123,134')
        dd_html = f'<div class="dd">▼{ddv:.0f}</div>' if ddv >= 0.5 else ''
        return f'<td class="hc" style="background:rgba({rgb},{a:.2f})"><div class="v">{v:+.0f}</div>{dd_html}</td>'

    def hcell(v, bold=False):
        if abs(v) < 0.005:
            return '<td class="z">·</td>'
        a = 0.12 + 0.78 * min(1.0, abs(v) / scale)
        rgb = '38,166,154' if v > 0 else '239,83,80'
        b = ' style2' if bold else ''
        return f'<td class="hc{b}" style="background:rgba({rgb},{a:.2f})">{v:+.0f}</td>'

    def plain(v, bold=True):
        col = '#26a69a' if v > 0 else ('#ef5350' if v < 0 else '#787b86')
        return f'<td class="num" style="color:{col};font-weight:{700 if bold else 400}">{v:+.0f}</td>'

    head = ('<tr class="hd"><th class="l">Rok</th>'
            + ''.join(f'<th>{m}</th>' for m in MONTHS_PL) + '<th>Rok Σ</th></tr>')
    body = []
    for y in years:
        body.append(f'<tr><td class="l yr">{y}</td>' + ''.join(ycell(y, m) for m in range(1, 13))
                    + plain(sum(port[y].values())) + '</tr>')
    col_sum = {m: sum(port[y][m] for y in years) for m in range(1, 13)}
    foot = [('<tr class="sep"><td class="l b">Σ / miesiąc</td>'
             + ''.join(hcell(col_sum[m], True) for m in range(1, 13)) + plain(sum(col_sum.values())) + '</tr>')]
    yrs_with = {m: sum(1 for y in years if f'{y}-{m:02d}' in all_keys) for m in range(1, 13)}
    col_avg = {m: (col_sum[m] / yrs_with[m]) if yrs_with[m] else 0.0 for m in range(1, 13)}
    scale_a = max((abs(col_avg[m]) for m in range(1, 13)), default=1.0) or 1.0

    def acell(v):
        if abs(v) < 0.005:
            return '<td class="z">·</td>'
        a = 0.12 + 0.78 * min(1.0, abs(v) / scale_a)
        rgb = '38,166,154' if v > 0 else '239,83,80'
        return f'<td class="hc style2" style="background:rgba({rgb},{a:.2f})">{v:+.0f}</td>'
    foot.append('<tr><td class="l" style="color:#e8c766;font-weight:700">Śr / miesiąc</td>'
                + ''.join(acell(col_avg[m]) for m in range(1, 13))
                + '<td class="num" style="color:#787b86;font-size:10px">odcisk<br>sezon.</td></tr>')

    # nakladki LW + COT (wyrownane do kolumn miesiecy)
    def sgcell(s, title=''):
        mp = {'long': ('▲', '#26a69a'), 'short': ('▼', '#ef5350'),
              'caution': ('~', '#e8c766'), 'neutral': ('•', '#787b86')}
        if not s:
            return '<td class="z" style="text-align:center">–</td>'
        ch, col = mp.get(s, ('?', '#787b86'))
        tt = f' title="{title}"' if title else ''
        return f'<td class="sg" style="color:{col}"{tt}>{ch}</td>'

    def ov_row(label, sig, source, titles=None):
        cells = ''.join(sgcell(sig[m] if m < len(sig) else None,
                               (titles[m] if titles and m < len(titles) else '')) for m in range(12))
        return (f'<tr><td class="l ov">{label}</td>' + cells
                + f'<td class="src">{source}</td></tr>')

    if lw or cot:
        groups = [('🥇 Złoto — nasze: DEP / RT / Okno Azji / Turtle', 'gold', 'gold'),
                  ('📈 US indeksy — nasze: PPK / BTFD / RSI + DAX (proxy)', 'sp_djia', 'nasdaq'),
                  ('💴 JPY — nasz: Adaptacja', 'usd', 'jpy')]
        foot.append('<tr><td colspan="14" class="ovhdr">🔭 Nakładki sezonowe — referencja historyczna '
                    '(nie nasz wynik): ▲ long · ▼ short · ~ ostrożność · • neutralnie</td></tr>')
        for title, lwk, cotk in groups:
            foot.append(f'<tr><td colspan="14" class="grp">{title}</td></tr>')
            la = (lw or {}).get('assets', {}).get(lwk)
            if la:
                foot.append(ov_row('LW · ' + la['label'], la['sig'], 'Larry Williams 2026'))
            cm = (cot or {}).get('markets', {}).get(cotk)
            if cm and not cm.get('error'):
                titles = [(f"% lat na plus: {cm['pct_up'][m]}%, śr Δ {cm['mean_chg'][m]} kontr."
                           if cm.get('pct_up') and cm['pct_up'][m] is not None else 'brak danych') for m in range(12)]
                foot.append(ov_row('COT · ' + cm['label'], cm['sig'], f"CFTC spek.net {cm.get('span', '')}", titles))

    # per-bot
    per_bot = []
    for t, d in sorted(bots.items(), key=lambda kv: -sum(kv[1].get('by_year', {}).values())):
        tot = sum(d.get('by_year', {}).values())
        cells = ''.join(plain(d.get('by_year', {}).get(y, 0.0), False) for y in years)
        per_bot.append(f'<tr><td class="l">{d.get("name", t)} <span class="dim">{d.get("symbol","")} {d.get("tf","")}</span></td>'
                       + cells + plain(tot) + f'<td class="num dim">{d.get("n", 0)}</td></tr>')
    for t, d in errs.items():
        per_bot.append(f'<tr class="err"><td class="l">{d.get("name", t)}</td>'
                       f'<td colspan="{len(years)+2}" style="color:#ef5350">błąd: {d.get("error")}</td></tr>')
    pb_head = ('<tr class="hd"><th class="l">Bot</th>'
               + ''.join(f'<th>{y}</th>' for y in years) + '<th>Razem €</th><th>n</th></tr>')

    n_ok, n_all = len(bots), len(bots) + len(errs)
    return (
        f'<div class="banner">🗓️ Backtest championów wstecz ile pozwalają dane ({n_ok}/{n_all} botów). '
        'Suma € miesięcznego P&amp;L portfela — każdy bot na bazie 10 000, ryzyko wg USTAWIENIA_FORWARD.</div>'
        '<div class="note">W komórce: <b>net €</b> (góra) + <b style="color:#ffb3ab">▼max DD</b> konta w tym '
        'miesiącu (obsunięcie wewnątrzmiesięczne, dół). <b>·</b> = brak transakcji. Miesiące <b>sprzed 2023 '
        'niedostępne</b> (dane brokera m1 od ~2023) → macierz to ~3,5 roku (3–4 próbki/mies. = cross-check). '
        'Głębszą historię dają nakładki <b>COT</b> (od 1986/2000) i cykle <b>Larry&#39;ego Williamsa</b>. '
        'Wiersz <b style="color:#e8c766">Śr / miesiąc</b> = nasz odcisk sezonowy do porównania z nakładkami.</div>'
        '<div class="scroll"><table class="grid"><thead>' + head + '</thead><tbody>'
        + ''.join(body) + '</tbody><tfoot>' + ''.join(foot) + '</tfoot></table></div>'
        '<div class="h2">Wkład roczny per bot</div>'
        '<div class="scroll"><table class="grid"><thead>' + pb_head + '</thead><tbody>'
        + ''.join(per_bot) + '</tbody></table></div>')


PAGE = """<!doctype html><html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sezonowość — backtest</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;background:#131722;color:#d1d4dc;font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif}}
.wrap{{max-width:1280px;margin:0 auto;padding:24px 16px 60px}}
h1{{font-size:22px;margin:0 0 2px;color:#e8eaed}}
.sub{{color:#787b86;font-size:12.5px;margin-bottom:18px}}
.banner{{margin:8px 0 6px;padding:10px 14px;background:#2a2e39;border-left:3px solid #e8c766;
  color:#c9cdd6;font-size:12.5px;font-weight:600;border-radius:0 4px 4px 0}}
.note{{margin:6px 0 10px;padding:10px 14px;background:#1e222d;border:1px solid #2a2e39;border-radius:6px;
  color:#9aa0ad;font-size:11.5px;line-height:1.65}}
.h2{{margin:22px 0 6px;color:#9aa0ad;font-size:12px;font-weight:600}}
.scroll{{overflow-x:auto;border-radius:6px}}
table.grid{{width:100%;border-collapse:collapse;font-size:12px;color:#c9cdd6}}
.grid th{{padding:6px 7px;text-align:right;background:#2a2e39;color:#9aa0ad;font-weight:600;white-space:nowrap}}
.grid th.l{{text-align:left}}
.grid td{{padding:4px 7px;text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
.grid td.l{{text-align:left;color:#d1d4dc}}
.grid td.yr{{font-weight:600}}
.grid td.z{{color:#3d414b}}
.grid td.hc{{color:#f0f2f4}}
.grid td.hc .v{{font-weight:600}}
.grid td.hc .dd{{color:#ffb3ab;font-size:9px;margin-top:1px}}
.grid td.hc.style2{{font-weight:700}}
.grid td.num{{padding:4px 9px}}
.grid tr.sep td{{border-top:2px solid #3a3e49}}
.grid td.sg{{text-align:center;font-weight:700}}
.grid td.ov{{color:#c9cdd6;font-size:11.5px}}
.grid td.src{{color:#787b86;font-size:10px;text-align:right}}
.grid td.ovhdr{{padding:9px 10px 3px;color:#8fa7ff;font-weight:700;font-size:11.5px;border-top:2px solid #3a3e49}}
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
    sub = (f"Miesięczny P&amp;L portfela {nb} botów (backtest championów) vs cykle COT / Larry Williams. "
           "Model: 1 bot = 1 konto 10k.")
    html = PAGE.format(sub=sub, section=section, ts=ts,
                       lwsrc=(lw or {}).get("source", "LW —"),
                       cotsrc=(cot or {}).get("source", "COT —"))
    out = os.path.join(HERE, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("OK ->", out, f"| {nb} botów, {len(html)} B")


if __name__ == "__main__":
    main()
