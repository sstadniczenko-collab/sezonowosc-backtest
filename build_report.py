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


def _pcell(v, first=False):
    """Komórka PROGNOZY (wyblakła, kursywa) — sezonowy avg × kierunek LW."""
    ps = ' pstart' if first else ''
    if v is None:
        return f'<td class="m pred{ps} nd2" title="brak danych do prognozy">·</td>'
    col = '#2e8f82' if v > 0 else ('#b0605e' if v < 0 else '#6a6e79')
    return f'<td class="m pred{ps}" style="color:{col}"><i>{v:+.0f}</i></td>'


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

    # ── PROGNOZA LW: Sie–Gru 2026 = sezonowy avg bota × kierunek LW ──
    PRED = [f'2026-{m:02d}' for m in range(8, 13) if f'2026-{m:02d}' not in axis]
    LWMAP = {'gdep': 'gold', 'grt': 'gold', 'trr': 'gold', 'turtle': 'gold',
             'daxl': 'sp_djia', 'orb': 'sp_djia', 'olb': 'sp_djia',
             'ppk': 'sp_djia', 'btfd': 'sp_djia', 'rsi': 'sp_djia', 'jpy': 'usd'}
    lw_assets = (lw or {}).get('assets', {})

    def _sgn(x):
        return 1 if x > 0 else (-1 if x < 0 else 0)

    def pred_for(tag, d):
        bm = d['by_month']
        sig = lw_assets.get(LWMAP.get(tag, ''), {}).get('sig')
        out = {}
        for pk in PRED:
            m = int(pk[5:7])
            vals = [bm[f'{Y}-{m:02d}'] for Y in ('2023', '2024', '2025') if f'{Y}-{m:02d}' in bm]
            if not vals:
                out[pk] = None; continue
            sa = sum(vals) / len(vals)
            lws = ({'long': 1, 'short': -1}.get(sig[m - 1], 0)) if (sig and m - 1 < len(sig)) else 0
            ss = _sgn(sa)
            k = 1.0 if (lws and lws == ss) else (0.3 if (lws and lws != ss) else 0.5)
            out[pk] = round(sa * k, 1)
        return out

    pred_by_bot, port_pred = {}, {pk: 0.0 for pk in PRED}
    for t, d in order:
        pr = pred_for(t, d)
        pred_by_bot[t] = pr
        for pk in PRED:
            if pr.get(pk) is not None:
                port_pred[pk] += pr[pk]

    # ── OŚ CZASU z podsumowaniem Σ€/% PO KAŻDYM roku ──
    year_months = {y: [mk for mk in axis if mk[:4] == y] for y in years}
    yr_net = {y: sum(port[mk] for mk in year_months[y]) for y in years}
    yr_active = {y: sum(1 for _, d in bots.items() if any(k[:4] == y for k in d['by_month'])) for y in years}

    def sc2(eur, pct, cls='ys'):
        if eur is None:
            return f'<td class="num {cls} dim">—</td><td class="num {cls} dim">—</td>'
        ec = '#26a69a' if eur > 0 else ('#ef5350' if eur < 0 else '#787b86')
        pc = '#26a69a' if (pct or 0) > 0 else ('#ef5350' if (pct or 0) < 0 else '#787b86')
        return (f'<td class="num {cls}" style="color:{ec};font-weight:700">{eur:+.0f}</td>'
                f'<td class="num {cls}" style="color:{pc};font-weight:700">{pct:+.0f}%</td>')

    h1 = ['<tr class="hd"><th class="stick l" rowspan="2">Strumień</th>']
    for y in years:
        h1.append(f'<th colspan="{len(year_months[y])+2}" class="ynew ygrp">{y}</th>')
    if PRED:
        h1.append(f'<th colspan="{len(PRED)+2}" class="predgrp">🔮 PROGNOZA LW (Sie–Gru 2026)</th>')
    h1.append('<th colspan="2" class="ygrp grand">CAŁOŚĆ</th></tr>')
    h2 = ['<tr class="hd">']
    for y in years:
        for mk in year_months[y]:
            m = int(mk[5:7])
            h2.append(f'<th class="m{" ynew" if m == 1 else ""}">{MONTHS_PL[m-1]}</th>')
        h2.append('<th class="ys">Σ€</th><th class="ys">%</th>')
    for i, pk in enumerate(PRED):
        h2.append(f'<th class="m pred{" pstart" if i == 0 else ""}">{MONTHS_PL[int(pk[5:7])-1]}*</th>')
    if PRED:
        h2.append('<th class="ys pred">Σ€</th><th class="ys pred">%</th>')
    h2.append('<th class="ys grand">Σ€</th><th class="ys grand">%</th></tr>')

    # portfel
    pscale = max((abs(port[mk]) for mk in axis), default=1.0) or 1.0
    prow = ['<tr class="port"><td class="stick l b">📊 Portfel (Σ)</td>']
    for y in years:
        for mk in year_months[y]:
            prow.append(_mcell(port[mk], pscale, dd.get(mk), int(mk[5:7]) == 1))
        prow.append(sc2(yr_net[y], yr_net[y] / (yr_active[y] * BASE) * 100 if yr_active[y] else 0))
    for i, pk in enumerate(PRED):
        prow.append(_pcell(port_pred.get(pk), i == 0))
    if PRED:
        pe = sum(port_pred.values())
        prow.append(sc2(pe, pe / (len(bots) * BASE) * 100, 'ys pred'))
    gt = sum(port.values())
    prow.append(sc2(gt, gt / (len(bots) * BASE) * 100, 'ys grand'))
    prow.append('</tr>')

    # boty
    brows = []
    for t, d in order:
        bm = d['by_month']
        cover = set()
        for yr, seg in (d.get('segs') or {}).items():
            if not seg.get('error'):
                cover.add('2026' if yr == '2026H1' else yr[:4])
        sc = max((abs(bm.get(mk, 0.0)) for mk in axis), default=1.0) or 1.0
        r = [f'<td class="stick l">{d.get("name", t)} <span class="dim">{d.get("symbol","")} {d.get("tf","")}</span></td>']
        for y in years:
            for mk in year_months[y]:
                mnew = int(mk[5:7]) == 1
                if cover and mk[:4] not in cover:
                    r.append(f'<td class="m nd{" ynew" if mnew else ""}" title="brak danych (timeout/nie policzony)">×</td>')
                else:
                    r.append(_mcell(bm.get(mk, 0.0), sc, None, mnew))
            if cover and y not in cover:
                r.append(sc2(None, None))
            else:
                ye = d.get('by_year', {}).get(y, sum(bm.get(mk, 0.0) for mk in year_months[y]))
                r.append(sc2(ye, ye / BASE * 100))
        prb = pred_by_bot.get(t, {})
        for i, pk in enumerate(PRED):
            r.append(_pcell(prb.get(pk), i == 0))
        if PRED:
            pv = [v for v in prb.values() if v is not None]
            r.append(sc2(sum(pv), sum(pv) / BASE * 100, 'ys pred') if pv else sc2(None, None, 'ys pred'))
        tot = sum(d.get('by_year', {}).values())
        r.append(sc2(tot, tot / BASE * 100, 'ys grand'))
        brows.append('<tr>' + ''.join(r) + '</tr>')
    ncols = len(axis) + 2 * len(years) + (len(PRED) + 2 if PRED else 0) + 2
    for t, d in errs.items():
        brows.append(f'<tr class="err"><td class="stick l">{d.get("name", t)}</td>'
                     f'<td colspan="{ncols}" style="color:#ef5350">błąd: {d.get("error")}</td></tr>')

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
              'do siebie — widać jego własny rytm). <b>·</b> = był handel w tym roku, ale brak transakcji w '
              'tym miesiącu (normalne dla rzadkich botów: grt/jpy ~15–25 tr./rok). '
              '<b style="color:#c98a8a">×</b> = brak danych (segment nie policzony — <b>GER40 i US100 za 2023</b>: '
              'ładowanie roku danych m1 timeoutuje = ściana obliczeniowa; złoto/JPY 2023 policzone). '
              'Miesiące <b>sprzed 2023 niedostępne</b> '
              '(dane brokera m1 od ~2023) → oś to ~3,5 roku = cross-check; głębszą historię dają nakładki '
              '<b>COT</b>/<b>LW</b> niżej. Przewiń oś w bok (suwak). '
              '<b style="color:#b9a0e0">🔮 Blok PROGNOZA (Sie–Gru 2026, kursywa)</b> = '
              'sezonowy średni bota dla danego miesiąca (2023–25) × kierunek LW '
              '(potwierdza ×1.0 / ostrożność ×0.5 / sprzeczny ×0.3). To <b>spekulacja</b>, '
              'nie backtest — magnituda z naszej historii, kierunek od Larry\'ego.</div>')
    return banner + timeline + year_tbl + seasonal


def _esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def render_corr(corr):
    if not corr:
        return ''

    def num(v, suf=''):
        if v is None:
            return '<td class="num dim">—</td>'
        col = '#26a69a' if v > 0 else ('#ef5350' if v < 0 else '#787b86')
        return f'<td class="num" style="color:{col}">{v}{suf}</td>'

    def verd(b):
        if not b or b.get('corr') is None:
            return ('—', '#787b86')
        c, e = b['corr'], b.get('edge_eur')
        if c >= 0.15 and (e is None or e > 0):
            return ('ZGODNY z cyklem', '#26a69a')
        if c <= -0.15 and (e is None or e < 0):
            return ('PRZECIW cyklowi', '#ef5350')
        return ('neutralnie / słabo', '#e8c766')

    rows = []
    for key, r in corr.items():
        for src, lab in (('lw', 'LW'), ('cot', 'COT')):
            b = r.get(src)
            if not b:
                continue
            vt, vc = verd(b)
            first = (f'<td class="l b" rowspan="2">{_esc(r["label"])} '
                     f'<span class="dim">{r["n_bots"]} bot · {r["n_months"]} mies</span></td>') if src == 'lw' else ''
            wr = (f'{b["wr_long"]}% / {b["wr_other"]}%' if b["wr_long"] is not None else '—')
            rows.append('<tr>' + first + f'<td class="l">{lab}</td>' + num(b['corr']) + num(b['edge_eur'], '€')
                        + f'<td class="num">{wr}</td>'
                        + f'<td class="l" style="color:{vc};font-weight:700">{vt}</td></tr>')
    head = ('<tr class="hd"><th class="l">Klasa</th><th class="l">Źródło</th><th>corr</th>'
            '<th>edge €/mies</th><th>WR long/reszta</th><th class="l">werdykt</th></tr>')
    return ('<div class="h2">🔗 Zgodność naszych botów z sezonowością (korelacja P&amp;L z biasem miesiąca)</div>'
            '<div class="note">corr = Pearson znaku sezonowego (+1 long / −1 short / 0) z miesięcznym P&amp;L klasy; '
            'edge = śr. P&amp;L w miesiącach long minus reszta. Dodatnie = gramy Z cyklem. <b>Wstępne</b> — '
            'backtest niekompletny, werdykt się zmieni po komplecie. COT = sezonowa zmiana pozycji spekulantów '
            '(≠ cena), interpretuj ostrożnie. To odpowiada na: czy nasz edge jedzie z sezonowością, czy wbrew.</div>'
            '<div class="scroll"><table class="grid"><thead>' + head + '</thead><tbody>'
            + ''.join(rows) + '</tbody></table></div>')


def render_forecast(fc):
    if not fc or not fc.get('items'):
        return ''
    rows = []
    curq = object()
    for it in fc['items']:
        if it.get('q') != curq:
            curq = it.get('q')
            rows.append(f'<tr><td colspan="5" class="grp">{_esc(curq or "Setupy krótkoterminowe (powtarzalne)")}</td></tr>')
        sig = it.get('sygnal', '')
        col = '#26a69a' if ('BULL' in sig or '📈' in sig) else ('#ef5350' if ('BEAR' in sig or '📉' in sig) else '#e8c766')
        rows.append('<tr>' + f'<td class="l">{_esc(it.get("okres",""))}</td>'
                    + f'<td class="l">{_esc(it.get("aktywo",""))}</td>'
                    + f'<td class="l" style="color:{col}">{_esc(sig)}</td>'
                    + f'<td class="l dim">{_esc(it.get("pewnosc",""))}</td>'
                    + f'<td class="l cyt">{_esc(it.get("cytat",""))}</td></tr>')
    head = ('<tr class="hd"><th class="l">Okres</th><th class="l">Aktywo</th><th class="l">Sygnał</th>'
            '<th class="l">Pewność</th><th class="l">Cytat Larry\'ego</th></tr>')
    return ('<div class="h2">🔮 Prognoza LW na przyszłość (2026) — co Larry przewiduje</div>'
            '<div class="note">To <b>predykcja</b> (cykle + sezonowość + fundamenty), nie backtest. Miesza część '
            '<b>powtarzalną</b> (sezonowość — można cofać/botować) z <b>rok-specyficzną</b> (decennial „rok-6", '
            '4-letni dołek maj–cze, 7-letni cykl złota) — tej drugiej NIE stosujemy do 2023–2025.</div>'
            '<div class="scroll"><table class="grid fc"><thead>' + head + '</thead><tbody>'
            + ''.join(rows) + '</tbody></table></div>')


def render_weekly(lw, cot, reality):
    """Oś tygodniowa 2026 (52 tyg, przewijana): LW + COT, strzałki ▲▼~•.
    Złoto/S&P = zwroty śród-miesięczne wg dat LW; reszta = miesięczny sygnał na tygodnie."""
    if not lw:
        return ''
    from datetime import date, timedelta
    d = date(2026, 1, 1)
    while d.weekday() != 0:            # pierwszy poniedziałek 2026
        d += timedelta(days=1)
    weeks = [d + timedelta(days=7 * i) for i in range(52)]
    mids = [w + timedelta(days=3) for w in weeks]   # czwartek = środek tygodnia
    lwa = lw.get('assets', {})

    # zwroty śród-miesięczne wg dat z Kalendarza LW (breakpointy)
    GOLD = [(date(2026, 1, 1), 'long'), (date(2026, 5, 15), 'caution'), (date(2026, 8, 15), 'long')]
    SPX = [(date(2026, 1, 1), 'long'), (date(2026, 2, 15), 'short'), (date(2026, 6, 16), 'long'),
           (date(2026, 8, 31), 'caution'), (date(2026, 10, 1), 'long')]

    def bp(bps, dt):
        s = None
        for st, sig in bps:
            if dt >= st:
                s = sig
        return s

    def mo(key, m):
        sig = lwa.get(key, {}).get('sig')
        return sig[m - 1] if sig and m - 1 < len(sig) else None

    def wsig(key, i):
        dt = mids[i]
        if key == 'gold':
            return bp(GOLD, dt)
        if key == 'sp_djia':
            return bp(SPX, dt)
        return mo(key, dt.month)

    cotm = (cot or {}).get('markets', {})

    def csig(key, i):
        c = cotm.get(key)
        if not c or c.get('error'):
            return None
        sig = c.get('sig'); m = mids[i].month
        return sig[m - 1] if sig and m - 1 < len(sig) else None

    def sg(s):
        mp = {'long': ('▲', '#26a69a'), 'short': ('▼', '#ef5350'),
              'caution': ('~', '#e8c766'), 'neutral': ('•', '#787b86')}
        if not s:
            return '<td class="wk z">–</td>'
        ch, col = mp.get(s, ('?', '#787b86'))
        return f'<td class="wk" style="color:{col};font-weight:700">{ch}</td>'

    # nagłówek: miesiąc (colspan) + dzień początku tygodnia
    h1 = ['<tr class="hd"><th class="stick l" rowspan="2">Aktywo</th>']
    seq = [m.month for m in mids]
    i = 0
    while i < len(seq):
        j = i
        while j < len(seq) and seq[j] == seq[i]:
            j += 1
        h1.append(f'<th colspan="{j-i}" class="ynew ygrp">{MONTHS_PL[seq[i]-1]}</th>')
        i = j
    h1.append('</tr>')
    h2 = ['<tr class="hd">'] + [f'<th class="wk{" ynew" if w.day <= 7 else ""}">{w.day}</th>' for w in weeks] + ['</tr>']

    rea = reality or {}

    def reasig(key, i):
        r = rea.get(key)
        if not r:
            return (None, False)
        mk = weeks[i].isoformat()
        wk = r.get('weekly', {})
        if mk in wk:
            return (wk[mk], False)                    # realne
        mn = r.get('monthly')
        return (mn[mids[i].month - 1] if mn else None, True)   # predykcja

    def cell(s, pred=False):
        if not s:
            return '<td class="wk z">–</td>'
        mp = {'long': ('▲', '#26a69a'), 'short': ('▼', '#ef5350'),
              'caution': ('~', '#e8c766'), 'neutral': ('•', '#787b86')}
        ch, col = mp.get(s, ('?', '#787b86'))
        ex = ';opacity:.5;font-style:italic' if pred else ''
        return f'<td class="wk" style="color:{col};font-weight:700{ex}">{ch}</td>'

    def dnum(s):
        return 1 if s == 'long' else (-1 if s == 'short' else 0)

    # key, label, lw_key, cot_key, reality_key, nota o cyklu
    PACKETS = [
        ('gold', '🥇 Złoto', 'gold', 'gold', 'gold', 'Cykl 7-letni + 44–50-miesięczny — LW: oba w fazie byczej 2026'),
        ('spx', '📈 S&P 500', 'sp_djia', 'sp500', 'spx', 'Cykl 4-letni → dołek maj–cze 2026 (punkt kupna); Decennial „rok-6" mocny H2'),
        ('ndx', '📈 Nasdaq 100', 'sp_djia', 'nasdaq', 'ndx', 'Jak S&P — 4-letni dołek maj–cze 2026'),
        ('usd', '💵 USD / DXY', 'usd', 'dxy', 'usd', 'Risk-off krótkoterminowo; długoterminowo w dół (Fed tnie stopy)'),
        ('oil', '🛢 Ropa WTI', 'oil', 'wti', 'oil', 'Cykl 10-letni → najsilniejsza fala zaczyna się późn. 2026'),
        ('bonds', '🏦 Obligacje (TLT/10Y)', 'bonds', 'bonds', 'bonds', 'Cykl 9-letni: stopy ↓ do 2030 → obligacje strukturalnie bycze'),
        ('btc', '₿ Bitcoin', 'btc', 'btc', 'btc', 'Cykl 4-letni (halving IV.2024) → szczyt zwykle 12–18 mies. po = 2025–26'),
        ('reits', '🏠 Nieruchomości', 'reits', None, 'reits', 'Cykl 10-letni → dołek ~koniec 2027 (LW: short cały 2026)'),
        ('silver', '🥈 Srebro', None, 'silver', 'silver', 'Metale — podąża za złotem, wyższa beta'),
        ('platinum', '⚪ Platyna', None, 'platinum', 'platinum', 'Metale szlachetne/przemysłowe'),
        ('palladium', '⚫ Pallad', None, 'palladium', 'palladium', 'Metale — cykl motoryzacyjny (katalizatory)'),
        ('copper', '🟫 Miedź', None, 'copper', 'copper', 'Cykl przemysłowy / globalny wzrost (Dr Copper)'),
        ('nikkei', '🗾 Nikkei', None, 'nikkei', 'nikkei', 'Koreluje z globalnymi akcjami + kurs JPY'),
        ('jpy', '💴 JPY (jen)', None, 'jpy', 'jpy', 'FX — bezpieczna przystań; słaby przy risk-on'),
        ('eur', '💶 EUR', None, 'eur', 'eur', 'FX'),
        ('gbp', '💷 GBP', None, 'gbp', 'gbp', 'FX'),
        ('aud', '🇦🇺 AUD', None, 'aud', 'aud', 'FX ryzykowna (proxy Chiny/surowce)'),
        ('cocoa', '🍫 Kakao', None, 'cocoa', 'cocoa', 'Miękkie — pogoda/podaż (Afryka Zach.)'),
        ('coffee', '☕ Kawa', None, 'coffee', 'coffee', 'Miękkie — pogoda/podaż (Brazylia)'),
    ]

    def has_cot(k):
        return bool(k and cotm.get(k) and not cotm[k].get('error'))

    body = []
    for key, label, lwk, cotk, rk, cyc in PACKETS:
        body.append(f'<tr><td colspan="53" class="pkt">{label} &nbsp; <span class="cyc">cykl: {cyc}</span></td></tr>')
        if lwk:
            body.append('<tr><td class="stick l sub">LW 2026</td>'
                        + ''.join(cell(wsig(lwk, i)) for i in range(52)) + '</tr>')
        if has_cot(cotk):
            body.append('<tr><td class="stick l sub">COT 2026</td>'
                        + ''.join(cell(csig(cotk, i)) for i in range(52)) + '</tr>')
        if rk and rea.get(rk):
            body.append('<tr><td class="stick l sub">Rzeczywistość / pred.</td>'
                        + ''.join(cell(*reasig(rk, i)) for i in range(52)) + '</tr>')
        agr = []
        for i in range(52):
            ss = []
            if lwk:
                ss.append(wsig(lwk, i))
            if has_cot(cotk):
                ss.append(csig(cotk, i))
            if rk and rea.get(rk):
                ss.append(reasig(rk, i)[0])
            nz = [dnum(s) for s in ss if s and dnum(s) != 0]
            if len(nz) >= 2 and all(x == nz[0] for x in nz):
                up = nz[0] > 0
                agr.append('<td class="wk" style="font-weight:800;color:{};background:rgba({},.22)">{}</td>'.format(
                    '#26a69a' if up else '#ef5350', '38,166,154' if up else '239,83,80', '▲' if up else '▼'))
            else:
                agr.append('<td class="wk z">·</td>')
        body.append('<tr><td class="stick l sub" style="color:#e8c766">✓ ZGODNOŚĆ</td>' + ''.join(agr) + '</tr>')

    return ('<div class="h2">🗓️ Sezonowość 2026 tydzień-po-tygodniu — pakiety per aktywo: '
            'LW vs COT vs Rzeczywistość — ▲ long · ▼ short · ~ ostrożność · • neutralnie</div>'
            '<div class="note"><b>Przewiń w bok.</b> Dla każdego aktywa 3 wiersze + zgodność: '
            '<b>LW 2026</b> (prognoza cykli Larry\'ego), <b>COT 2026</b> (sezonowa zmiana pozycji spekulantów), '
            '<b>Rzeczywistość/pred.</b> — <b>realne</b> tygodniowe ruchy ceny sty–lip 2026, od sierpnia '
            '<i>predykcja</i> (kursywa/wyblakłe) = sezonowy wzorzec cenowy tego aktywa. Wiersz '
            '<b style="color:#e8c766">✓ ZGODNOŚĆ</b> = tydzień, gdzie ≥2 z 3 sygnałów wskazują ten sam kierunek '
            '(tam sezonowość najmocniej pokrywa się z rzeczywistością). <b>Złoto/S&P</b> mają zwroty śród-miesięczne '
            'wg dat LW; reszta LW/COT — miesięcznie na tygodnie. <b>cykl:</b> przy każdym aktywie = gdzie jesteśmy '
            'w cyklu 4–10-letnim (wg LW). JPY/rzeczywistość = siła jena (odwrotność USDJPY).</div>'
            '<div class="scroll"><table class="grid"><thead>' + ''.join(h1) + ''.join(h2)
            + '</thead><tbody>' + ''.join(body) + '</tbody></table></div>')


def render_swing(sw):
    if not sw:
        return ''
    mg, fl, order, names = sw['managed'], sw['flat'], sw['order'], sw['bot_names']
    wall = sw['wall_eur']

    def rc(r):
        if r == 0:
            return '<td class="rk off" title="OFF w tym miesiącu">—</td>'
        cls = 'full' if r >= sw['base_risk'] else 'red'
        return f'<td class="rk {cls}">{r:.2f}</td>'

    h = ('<tr class="hd"><th class="stick l">Miesiąc 2026</th>'
         + ''.join(f'<th title="{names.get(t, t)}">{t}</th>' for t in order)
         + '<th>Δ mies. €</th><th>Equity €</th><th>DD %</th><th>do ściany €</th></tr>')
    rows = []
    for r in mg['rows']:
        pc = ' pred' if r['src'] == 'pred' else ''
        cells = ''.join(rc(r['perbot'][t]['risk']) for t in order)
        dw = r['dist_wall']
        ddc = '#ef5350' if r['dd_pct'] > 7 else ('#e8c766' if r['dd_pct'] > 4 else '#787b86')
        dwc = '#26a69a' if dw > 16000 else ('#e8c766' if dw > 8000 else '#ef5350')
        star = '*' if r['src'] == 'pred' else ''
        rows.append(f'<tr class="{pc}"><td class="stick l">{r["label"]}{star}</td>' + cells
                    + _num(r['pnl'])
                    + f'<td class="num" style="color:#e8eaed;font-weight:700">{r["equity"]:,.0f}</td>'
                    + f'<td class="num" style="color:{ddc}">{r["dd_pct"]:.1f}%</td>'
                    + f'<td class="num" style="color:{dwc};font-weight:700">{dw:,.0f}</td></tr>')

    rr = sw['rules']
    rules_rows = []
    for t in order:
        x = rr[t]
        off = ', '.join(x['off_months']) or '—'
        red = ', '.join(x['reduced_months']) or '—'
        rules_rows.append(
            f'<tr><td class="l">{_esc(x["name"])} <span class="dim">{_esc(x["symbol"])} {_esc(x["tf"])}</span></td>'
            f'<td class="l">{x["direction"]}</td>'
            f'<td class="num">{x["champ_risk"]:.2f}→{x["base_risk"]:.2f}%</td>'
            f'<td class="l" style="color:#ef5350">{_esc(off)}</td>'
            f'<td class="l" style="color:#e8c766">{_esc(red)}</td>'
            f'<td class="l dim" style="font-size:11px">{_esc(x["ftmo_note"])}</td></tr>')
    rules_head = ('<tr class="hd"><th class="l">Bot</th><th class="l">Kierunek</th>'
                  '<th>ryzyko champ→baza</th><th class="l">miesiące OFF</th>'
                  '<th class="l">miesiące redukcja 0.20%</th><th class="l">warunek FTMO</th></tr>')

    def verdict(x):
        return ('#26a69a', 'OK — z buforem') if not x['breach'] and x['max_dd_pct'] < 8 else \
               (('#e8c766', 'ryzykownie blisko ściany') if not x['breach'] else ('#ef5350', 'ŚCIANA PRZEBITA'))
    mc, mv = verdict(mg); fc, fv = verdict(fl)
    return (
        '<div class="h2">🏦 Symulacja konta FTMO SWING 80 000 € — 2026 (dobór ryzyka per bot / miesiąc)</div>'
        '<div class="note">Swing = wolno trzymać przez weekend i newsy → CAŁY portfel 11 botów (nie 3 jak Normal). '
        f'Twarda ściana: equity nigdy ≤ <b>{wall:,.0f} €</b> (−10%). Bazowe ryzyko <b>{sw["base_risk"]}%</b>/trade '
        '(prop, MC iter.#35). <b>Dobór</b>: bot OFF w miesiącach, gdzie historycznie (2023–25) mocno tracił; '
        'redukcja 0.20% gdy śr &lt;0 lub LW ostrzega (long-only). H1 (sty–lip) = realny backtest, '
        '<b>H2 (sie–gru)* = prognoza LW</b> (spekulacja). Zielone = pełne 0.33%, żółte = 0.20%, — = OFF. '
        'Uwaga: to equity MIESIĘCZNE — dzienny limit −5% (−4000€) wymaga danych dziennych; tu proxy.</div>'
        f'<div class="note" style="border-color:{mc}"><b style="color:{mc}">Plan zarządzany: koniec '
        f'{mg["end_equity"]:,.0f}€ ({mg["ret_pct"]:+.1f}%), maxDD {mg["max_dd_pct"]:.1f}% → {mv}.</b> '
        f'&nbsp;|&nbsp; <span style="color:{fc}">Flat 0.33% all-on: {fl["end_equity"]:,.0f}€ ({fl["ret_pct"]:+.1f}%), '
        f'maxDD {fl["max_dd_pct"]:.1f}% → {fv}</span> — dobór sezonowy tnie DD (bezpieczniej), flat da więcej '
        'ale ociera się o ścianę.</div>'
        '<div class="scroll"><table class="grid tl"><thead>' + h + '</thead><tbody>' + ''.join(rows)
        + '</tbody></table></div>'
        '<div class="h2">Warunki / parametry per bot (pod tabelą)</div>'
        '<div class="scroll"><table class="grid"><thead>' + rules_head + '</thead><tbody>'
        + ''.join(rules_rows) + '</tbody></table></div>')


def render_next2(sw):
    """Harmonogram ryzyka per bot do końca roku: wiersz=bot, kolumny=miesiące (parametr/miesiąc)."""
    if not sw:
        return ''
    from datetime import datetime as _DT, timezone as _TZ
    nowm = _DT.now(_TZ.utc).month
    mg = {r['m']: r for r in sw['managed']['rows']}
    months = [m for m in range(nowm, 13) if m in mg]
    if not months:
        return ''
    order, rules, base = sw['order'], sw['rules'], sw['base_risk']

    def rcell(v, prev=None):
        chg = ' chg' if (prev is not None and abs(v - prev) > 1e-9) else ''
        if v == 0:
            return f'<td class="rk off{chg}">OFF</td>'
        cls = 'full' if v >= base else 'red'
        return f'<td class="rk {cls}{chg}">{v:.2f}</td>'

    head = ('<tr class="hd"><th class="stick l">Bot / symbol / wykres</th>'
            + ''.join(f'<th>{MONTHS_PL[m-1]}</th>' for m in months) + '</tr>')
    rows = []
    for t in order:
        x = rules[t]
        cells = []
        prev = None
        for m in months:
            v = mg[m]['perbot'][t]['risk']
            cells.append(rcell(v, prev))
            prev = v
        rows.append(f'<tr><td class="stick l">{_esc(x["name"])} '
                    f'<span class="dim">{_esc(x["symbol"])} {_esc(x["tf"])}</span></td>' + ''.join(cells) + '</tr>')
    return ('<div class="h2">⚙️ Harmonogram ryzyka per bot — do końca 2026 (miesiąc → parametr)</div>'
            '<div class="note">Ryzyko %/bota w każdym miesiącu aż do grudnia — to <b>jedyny parametr, który '
            'zmienia się miesięcznie</b>; reszta stała (pełne arkusze: <code>FORWARD_962/ftmo_swing_80k</code>, '
            'plik per bot). <b>OFF</b> = zatrzymaj instancję na ten miesiąc. Zielone 0.33% / żółte 0.20% / OFF; '
            'ramka = zmiana vs poprzedni miesiąc. Konto startuje w sierpniu. Plan z symulacji Swing wyżej.</div>'
            '<div class="scroll"><table class="grid tl"><thead>' + head + '</thead><tbody>'
            + ''.join(rows) + '</tbody></table></div>')


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
.grid td.nd{{color:#c98a8a;text-align:center;background:repeating-linear-gradient(45deg,#241a1a,#241a1a 3px,#1c1616 3px,#1c1616 6px)}}
.grid td.pred,.grid th.pred{{background:#1a1622;font-style:italic}}
.grid th.pred{{color:#b9a0e0}}
.grid .pstart{{border-left:3px solid #6a4a8a}}
.grid th.predgrp{{background:#2a2440;color:#b9a0e0;text-align:center;border-left:3px solid #6a4a8a}}
.grid td.nd2{{color:#4a4550}}
.grid td.ys,.grid th.ys{{background:#20242e;border-left:1px solid #3a3e49;min-width:56px}}
.grid td.ys.grand,.grid th.ys.grand{{background:#2f3440}}
.grid td.ys.pred,.grid th.ys.pred{{background:#221c2e}}
.grid td.rk{{text-align:center;min-width:40px}}
.grid td.rk.full{{background:rgba(38,166,154,.25);color:#7fd8cc;font-weight:600}}
.grid td.rk.red{{background:rgba(232,199,102,.20);color:#e8c766}}
.grid td.rk.off{{color:#4a4e59}}
.grid td.rk.chg{{box-shadow:inset 2px 0 0 #8fa7ff}}
.grid td.wk,.grid th.wk{{min-width:22px;text-align:center;padding:3px 2px}}
.grid td.pkt{{padding:9px 10px 3px;background:#20242e;border-top:2px solid #3a3e49;color:#e8eaed;font-weight:700;font-size:12.5px}}
.grid td.pkt .cyc{{color:#8fa7ff;font-weight:400;font-size:11px}}
.grid td.sub{{padding-left:18px;color:#9aa0ad;font-size:11px}}
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
.grid.fc td{{white-space:normal;vertical-align:top}}
.grid td.cyt{{color:#9aa0ad;font-size:11px;max-width:520px;font-style:italic}}
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
    corr = load("corr.json")
    fc = load("lw_forecast.json")
    sw = load("ftmo_swing.json")
    reality = load("reality_2026.json")
    section = (render_section(mbt, lw, cot) + render_corr(corr) + render_forecast(fc)
               + render_weekly(lw, cot, reality) + render_swing(sw) + render_next2(sw))
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
