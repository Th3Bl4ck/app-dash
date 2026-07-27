#!/usr/bin/env python3
"""Genera la dashboard GIORNALIERA intraday per XAU (oro) come file HTML autonomo.

Contenuto intraday: news di oggi (placeholder ricorrente), livelli opzioni (GEX),
livelli di rottura (PDH/PDL/PDC), livelli di range (pivot floor-trader) + banda
range attesa (ATR), scenari breakout/breakdown/range, bias vs pivot centrale.
Autonomo (yfinance + InsiderFinance), pensato per girare anche in cloud pulito.
"""
from __future__ import annotations
import json, urllib.request, datetime as dt
import pandas as pd, yfinance as yf

TODAY = dt.date.today()
_MESI = ["gen","feb","mar","apr","mag","giu","lug","ago","set","ott","nov","dic"]
_GIORNI = ["lunedì","martedì","mercoledì","giovedì","venerdì","sabato","domenica"]
def _itdate(d): return f"{_GIORNI[d.weekday()]} {d.day} {_MESI[d.month-1]} {d.year}"

def fmt(v, dec=0):
    return f"{v:,.{dec}f}".replace(",", "§").replace(".", ",").replace("§", ".")

def gex_levels(ticker):
    url = f"https://cf.insiderfinance.io/v1/gex?ticker={ticker}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        obj = json.loads(urllib.request.urlopen(req, timeout=15).read().decode())
        opts = obj.get("options", [])
        if not opts: return None
        agg = {}
        for o in opts:
            try:
                k = float(o["strike"]); cp = str(o.get("cp","")).upper()[:1]
                w = float(o.get("gamma",0) or 0)*float(o.get("openInterest",0) or 0)
            except Exception: continue
            agg[(k,cp)] = agg.get((k,cp),0.0)+w
        calls = {k:v for (k,c),v in agg.items() if c=="C"}
        puts  = {k:v for (k,c),v in agg.items() if c=="P"}
        if not calls or not puts: return None
        return {"call_wall": round(max(calls,key=calls.get)),
                "put_wall": round(max(puts,key=puts.get))}
    except Exception:
        return None

def _rebuild_prev_day(day):
    """OHLC della sessione `day` ricostruito dalle barre a 15m (fallback)."""
    try:
        i = yf.download("GC=F", period="7d", interval="15m", auto_adjust=False, progress=False).dropna()
        if isinstance(i.columns, pd.MultiIndex): i.columns = i.columns.get_level_values(0)
        bars = i[i.index.date == day]
        if len(bars) < 10: return None
        return float(bars["High"].max()), float(bars["Low"].min()), float(bars["Close"].iloc[-1])
    except Exception:
        return None

def analyze():
    d = yf.download("GC=F", period="60d", interval="1d", auto_adjust=False, progress=False)
    d = d.dropna()
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    # sessione precedente = ultima barra giornaliera completa
    last_idx = d.index[-1].date()
    prev = d.iloc[-2] if last_idx == TODAY else d.iloc[-1]
    po, ph, pl, pc = (float(prev[k]) for k in ("Open","High","Low","Close"))
    # sanitizza OHLC (a volte il feed dà Close fuori da [Low,High])
    PDH = max(ph, po, pc); PDL = min(pl, po, pc); PDC = pc
    # ATR(14)
    h, l, c = d["High"], d["Low"], d["Close"]
    tr = pd.concat([(h-l), (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    atr = float(tr.tail(14).mean())
    # a volte la barra giornaliera arriva degenerata (O~H~L~C): ricostruisce da intraday
    prev_date = d.index[-2].date() if last_idx == TODAY else last_idx
    if PDH - PDL < 0.25 * atr:
        rb = _rebuild_prev_day(prev_date)
        if rb: PDH, PDL, PDC = rb
    # pivot floor-trader dalla sessione precedente
    PP = (PDH+PDL+PDC)/3
    R1, S1 = 2*PP-PDL, 2*PP-PDH
    R2, S2 = PP+(PDH-PDL), PP-(PDH-PDL)
    R3, S3 = PDH+2*(PP-PDL), PDL-2*(PDH-PP)
    # intraday: spot, open oggi, high/low oggi
    spot = PDC; op = PDC; th = PDH; tl = PDL
    try:
        i = yf.download("GC=F", period="2d", interval="5m", auto_adjust=False, progress=False).dropna()
        if isinstance(i.columns, pd.MultiIndex): i.columns = i.columns.get_level_values(0)
        spot = float(i["Close"].iloc[-1])
        today_bars = i[i.index.date == i.index[-1].date()]
        if len(today_bars):
            op = float(today_bars["Open"].iloc[0]); th = float(today_bars["High"].max()); tl = float(today_bars["Low"].min())
    except Exception:
        pass
    return dict(spot=spot, op=op, th=th, tl=tl, PDH=PDH, PDL=PDL, PDC=PDC, atr=atr,
                PP=PP, R1=R1, R2=R2, R3=R3, S1=S1, S2=S2, S3=S3,
                exp_lo=op-atr, exp_hi=op+atr, gap=op-PDC, gex=gex_levels("GLD"))

def ladder(a):
    spot = a["spot"]
    marks = [
        (a["R2"],"res","R2"),(a["R1"],"res","R1"),(a["PDH"],"res","PDH · rottura"),
        (a["PP"],"piv","Pivot PP"),
        (a["S1"],"sup","S1"),(a["S2"],"sup","S2"),(a["PDL"],"sup","PDL · rottura"),
    ]
    if a["gex"]:
        marks.append((a["gex"]["call_wall"],"res","Call Wall"))
        marks.append((a["gex"]["put_wall"],"sup","Put Wall"))
    prices=[m[0] for m in marks]+[spot,a["exp_lo"],a["exp_hi"]]
    hi=max(prices)*1.002; lo=min(prices)*0.998; span=hi-lo
    top=lambda p:(hi-p)/span*100
    band=f'<div class="band" style="top:{top(a["exp_hi"]):.1f}%;height:{top(a["exp_lo"])-top(a["exp_hi"]):.1f}%"><span class="btag">RANGE ATTESO (ATR)</span></div>'
    rows=[]
    for p,kind,tag in sorted(marks,key=lambda z:-z[0]):
        cls={"res":"res","sup":"sup","piv":"piv"}[kind]
        rows.append(f'<div class="lvl {cls}" style="top:{top(p):.1f}%"><span class="px">{fmt(p)}</span><span class="line"></span><span class="tag">{tag}</span></div>')
    rows.append(f'<div class="lvl spot" style="top:{top(spot):.1f}%"><span class="px">{fmt(spot,1)}</span><span class="line"></span><span class="tag">◄ SPOT</span></div>')
    return band+"".join(rows)

def main():
    a=analyze()
    up = a["spot"]>=a["PP"]
    bias_cls,bias = ("up","▲ BIAS LONG · sopra il pivot") if up else ("down","▼ BIAS SHORT · sotto il pivot")
    gap = a["gap"]; gap_txt=f"{'+' if gap>=0 else ''}{fmt(gap,1)}"
    if a["gex"]:
        gexrows=f'<div class="kv"><span class="k">Call Wall</span><span class="v" style="color:var(--down)">{fmt(a["gex"]["call_wall"])}</span></div><div class="kv"><span class="k">Put Wall</span><span class="v" style="color:var(--up)">{fmt(a["gex"]["put_wall"])}</span></div>'
        gexnote='Magneti opzioni di oggi (fonte InsiderFinance).'
    else:
        gexrows='<div class="kv"><span class="k">Call / Put Wall</span><span class="v" style="color:var(--dim)">n/d</span></div>'
        gexnote='Feed InsiderFinance <b>non disponibile</b> ora. Ricontrolla /gex a mercati aperti.'
    html=TEMPLATE.format(
        updated=_itdate(TODAY), spot=fmt(a["spot"],1),
        bias_cls=bias_cls, bias=bias,
        gap=gap_txt, gap_cls=("pos" if gap>=0 else "neg"),
        exp_lo=fmt(a["exp_lo"]), exp_hi=fmt(a["exp_hi"]), atr=fmt(a["atr"]),
        pp=fmt(a["PP"]), pos=("sopra" if up else "sotto"),
        pdh=fmt(a["PDH"]), pdl=fmt(a["PDL"]), pdc=fmt(a["PDC"]),
        r1=fmt(a["R1"]), r2=fmt(a["R2"]), s1=fmt(a["S1"]), s2=fmt(a["S2"]),
        ladder=ladder(a), gexrows=gexrows, gexnote=gexnote,
        bull=f'{fmt(a["PDH"])} → {fmt(a["R1"])} → {fmt(a["R2"])}',
        bear=f'{fmt(a["PDL"])} → {fmt(a["S1"])} → {fmt(a["S2"])}',
        rng=f'{fmt(a["S1"])} ⇄ {fmt(a["R1"])}')
    open("xau-daily.html","w").write(html)
    print("XAU daily", fmt(a["spot"],1), "PP", fmt(a["PP"]), "PDH", fmt(a["PDH"]), "PDL", fmt(a["PDL"]), "ATR", fmt(a["atr"]), "gex", a["gex"])
    print("scritto: xau-daily.html")

TEMPLATE = r'''<title>XAU intraday — {updated}</title>
<style>
  :root{{--bg:#0a0a0b;--surface:#151516;--surface-2:#1e1e20;--border:#2c2c2f;--text:#ececea;--dim:#9a9a97;--faint:#68686a;
    --accent:#c8a24b;--accent-soft:rgba(200,162,75,.13);--up:#3fa372;--up-soft:rgba(63,163,114,.14);--down:#d0554f;--down-soft:rgba(208,85,79,.14);--warn:#e0913f;
    --font-mono:ui-monospace,"SF Mono","JetBrains Mono",Menlo,Consolas,monospace;--font-sans:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;}}
  :root[data-theme="light"]{{--bg:#f7f5f0;--surface:#fff;--surface-2:#f1ede3;--border:#e2dccd;--text:#241f16;--dim:#6b6353;--faint:#9a917f;--accent:#9d7a2b;--accent-soft:rgba(157,122,43,.12);--up:#2f8a5d;--up-soft:rgba(47,138,93,.12);--down:#bd453f;--down-soft:rgba(189,69,63,.12);--warn:#b26f22;}}
  @media (prefers-color-scheme:light){{:root:not([data-theme="dark"]){{--bg:#f7f5f0;--surface:#fff;--surface-2:#f1ede3;--border:#e2dccd;--text:#241f16;--dim:#6b6353;--faint:#9a917f;--accent:#9d7a2b;--accent-soft:rgba(157,122,43,.12);--up:#2f8a5d;--down:#bd453f;--warn:#b26f22;}}}}
  *{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--text);font-family:var(--font-sans);line-height:1.5;-webkit-font-smoothing:antialiased;background-image:radial-gradient(120% 90% at 100% 0%,var(--accent-soft),transparent 55%)}}
  .wrap{{max-width:1180px;margin:0 auto;padding:clamp(18px,4vw,40px)}}
  .mono{{font-family:var(--font-mono);font-variant-numeric:tabular-nums}}
  .eyebrow{{font-family:var(--font-mono);font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:var(--accent)}}
  .label{{font-family:var(--font-mono);font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--dim)}}
  header{{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:20px;padding-bottom:22px;border-bottom:1px solid var(--border)}}
  h1{{font-size:clamp(28px,6vw,48px);margin:.15em 0 0;letter-spacing:-.01em;font-weight:800}} h1 .pair{{color:var(--dim);font-weight:500}}
  .spotbox{{text-align:right}} .spot{{font-family:var(--font-mono);font-size:clamp(26px,5vw,42px);font-weight:700;font-variant-numeric:tabular-nums;line-height:1}} .spot .cur{{color:var(--dim);font-size:.5em;margin-right:.3em}}
  .badge{{display:inline-flex;align-items:center;gap:6px;margin-top:8px;padding:4px 10px;border-radius:999px;font-family:var(--font-mono);font-size:12px;font-weight:600}}
  .badge.up{{background:var(--up-soft);color:var(--up);border:1px solid color-mix(in srgb,var(--up) 30%,transparent)}}
  .badge.down{{background:var(--down-soft);color:var(--down);border:1px solid color-mix(in srgb,var(--down) 30%,transparent)}}
  .tiles{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:22px 0}}
  .tile{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:14px 16px}}
  .tile .v{{font-family:var(--font-mono);font-size:clamp(17px,2.3vw,22px);font-weight:700;font-variant-numeric:tabular-nums;margin-top:4px}}
  .tile .sub{{font-size:12px;color:var(--dim);margin-top:2px}} .neg{{color:var(--down)}} .pos{{color:var(--up)}} .amb{{color:var(--accent)}}
  .grid{{display:grid;grid-template-columns:minmax(290px,1fr) 1.35fr;gap:16px;align-items:start}}
  .card{{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:18px}}
  .card h2{{font-size:13px;font-family:var(--font-mono);letter-spacing:.12em;text-transform:uppercase;color:var(--dim);margin:0 0 14px;font-weight:600;display:flex;gap:8px}} .card h2 .n{{color:var(--accent);font-weight:700}}
  .ladder{{position:relative;height:520px;margin:6px 4px 0}}
  .band{{position:absolute;left:0;right:0;background:var(--accent-soft);border-top:1px dashed color-mix(in srgb,var(--accent) 35%,transparent);border-bottom:1px dashed color-mix(in srgb,var(--accent) 35%,transparent)}}
  .band .btag{{position:absolute;right:0;top:50%;transform:translateY(-50%);font-family:var(--font-mono);font-size:10px;letter-spacing:.08em;color:var(--accent);background:var(--bg);padding:2px 6px;border-radius:6px}}
  .lvl{{position:absolute;left:0;right:0;display:flex;align-items:center;gap:8px;transform:translateY(-50%)}}
  .lvl .line{{flex:1;height:0;border-top:1.5px solid var(--l);opacity:.9}}
  .lvl .px{{font-family:var(--font-mono);font-size:13px;font-weight:700;font-variant-numeric:tabular-nums;color:var(--l);min-width:52px;text-align:right}}
  .lvl .tag{{font-family:var(--font-mono);font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:var(--dim);white-space:nowrap}}
  .lvl.res{{--l:var(--down)}} .lvl.sup{{--l:var(--up)}} .lvl.piv{{--l:var(--accent)}} .lvl.piv .line{{border-top-style:dashed}}
  .lvl.spot{{--l:var(--accent);z-index:3}} .lvl.spot .line{{border-top-width:2px}} .lvl.spot .px{{font-size:15px;background:var(--accent);color:#0a0a0b;padding:2px 8px;border-radius:6px;min-width:0}} .lvl.spot .tag{{color:var(--accent);font-weight:700}}
  .lvl.piv .px{{font-weight:800}}
  .blackout{{display:flex;gap:10px;background:var(--surface-2);border:1px dashed var(--border);border-radius:10px;padding:10px 12px;font-size:13px;color:var(--dim)}}
  .kv{{display:flex;justify-content:space-between;align-items:baseline;gap:10px;padding:8px 0;border-bottom:1px solid var(--border)}} .kv:last-child{{border-bottom:0}}
  .kv .k{{font-size:13px;color:var(--dim)}} .kv .v{{font-family:var(--font-mono);font-variant-numeric:tabular-nums;font-weight:700}}
  .grp{{margin-bottom:6px}} .grp .lab{{font-family:var(--font-mono);font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--accent);margin:10px 0 2px}}
  .gexnote{{font-size:12.5px;color:var(--dim);margin-top:8px}} .gexnote b{{color:var(--text)}}
  .scen{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:16px}}
  .sc{{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:16px;border-top:3px solid var(--edge)}}
  .sc.up{{--edge:var(--up)}} .sc.range{{--edge:var(--accent)}} .sc.down{{--edge:var(--down)}}
  .sc h3{{margin:0 0 6px;font-size:15px}} .sc .trig{{font-family:var(--font-mono);font-size:12px;color:var(--dim);margin-bottom:10px}}
  .sc .path{{font-family:var(--font-mono);font-size:13px;font-weight:700;font-variant-numeric:tabular-nums}}
  .sc.up .path{{color:var(--up)}} .sc.range .path{{color:var(--accent)}} .sc.down .path{{color:var(--down)}}
  .hero{{margin-top:16px;background:linear-gradient(90deg,var(--accent-soft),transparent);border:1px solid var(--border);border-left:3px solid var(--accent);border-radius:12px;padding:14px 16px;font-size:14px}} .hero b{{font-family:var(--font-mono)}}
  footer{{margin-top:24px;padding-top:16px;border-top:1px solid var(--border);font-size:12px;color:var(--faint);line-height:1.6}}
  .disc{{background:var(--surface-2);border:1px solid var(--border);border-radius:10px;padding:10px 12px;margin-bottom:12px;color:var(--dim);font-size:12.5px}}
  @media (max-width:820px){{.tiles{{grid-template-columns:repeat(2,1fr)}}.grid{{grid-template-columns:1fr}}.scen{{grid-template-columns:1fr}}}}
</style>
<div class="wrap">
  <header>
    <div><div class="eyebrow">Intraday · {updated}</div><h1>XAU<span class="pair">/USD · giornaliera</span></h1></div>
    <div class="spotbox"><div class="label">Spot · GC=F</div><div class="spot"><span class="cur">$</span>{spot}</div><div class="badge {bias_cls}">{bias}</div></div>
  </header>
  <section class="tiles">
    <div class="tile"><div class="label">Gap vs ieri</div><div class="v {gap_cls}">{gap}</div><div class="sub">apertura vs chiusura</div></div>
    <div class="tile"><div class="label">Range atteso oggi</div><div class="v amb">{exp_lo}–{exp_hi}</div><div class="sub">open ± ATR ({atr})</div></div>
    <div class="tile"><div class="label">Pivot centrale</div><div class="v">{pp}</div><div class="sub">prezzo {pos} il pivot</div></div>
    <div class="tile"><div class="label">Ieri (PDH / PDL)</div><div class="v">{pdh}<span style="color:var(--dim)"> / </span>{pdl}</div><div class="sub">chiusura {pdc}</div></div>
  </section>
  <div class="grid">
    <div class="card"><h2><span class="n">◆</span> Livelli intraday</h2><div class="ladder">{ladder}</div></div>
    <div style="display:flex;flex-direction:column;gap:16px">
      <div class="card"><h2><span class="n">▤</span> News di oggi</h2>
        <div class="blackout">Controlla gli eventi ad alto impatto di <b>oggi</b> su Investing.com / Financial Juice (CPI, Fed, dati lavoro). Nei giorni senza dati, comanda il flusso tecnico + GEX.</div></div>
      <div class="card"><h2><span class="n">▚</span> Mappa livelli</h2>
        <div class="grp"><div class="lab">Opzioni (GEX)</div>{gexrows}</div>
        <div class="grp"><div class="lab">Rottura (breakout)</div>
          <div class="kv"><span class="k">PDH · massimo ieri</span><span class="v" style="color:var(--down)">{pdh}</span></div>
          <div class="kv"><span class="k">PDL · minimo ieri</span><span class="v" style="color:var(--up)">{pdl}</span></div></div>
        <div class="grp"><div class="lab">Range (pivot)</div>
          <div class="kv"><span class="k">R2 / R1</span><span class="v">{r2} / {r1}</span></div>
          <div class="kv"><span class="k">Pivot PP</span><span class="v" style="color:var(--accent)">{pp}</span></div>
          <div class="kv"><span class="k">S1 / S2</span><span class="v">{s1} / {s2}</span></div></div>
        <div class="gexnote">{gexnote}</div></div>
    </div>
  </div>
  <div class="hero">🎯 <b>Bias del giorno vs pivot {pp}.</b> Trigger di rottura: <b>{pdh}</b> (sopra = spinta) / <b>{pdl}</b> (sotto = scarico). Dentro il range atteso {exp_lo}–{exp_hi} favorito il gioco mean-revert sui pivot.</div>
  <div class="scen">
    <div class="sc up"><h3>Breakout long</h3><div class="trig">sopra PDH {pdh}</div><div class="path">{bull}</div></div>
    <div class="sc range"><h3>Range</h3><div class="trig">tra S1 e R1 attorno al pivot</div><div class="path">{rng}</div></div>
    <div class="sc down"><h3>Breakdown</h3><div class="trig">sotto PDL {pdl}</div><div class="path">{bear}</div></div>
  </div>
  <footer>
    <div class="disc">⚠️ Analisi informativa/educativa — <b>non è consulenza finanziaria</b>. Livelli e scenari sono spunti; l'esecuzione e il rischio restano tuoi.</div>
    Rigenerata automaticamente il {updated} · dati live yfinance (GC=F, daily+5m). Pivot floor-trader dalla sessione precedente. GEX: InsiderFinance (best-effort).
  </footer>
</div>'''

if __name__ == "__main__":
    main()
