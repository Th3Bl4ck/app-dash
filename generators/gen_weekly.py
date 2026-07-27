#!/usr/bin/env python3
"""Genera le due dashboard settimanali (XAU e SP500) come file HTML autonomi.

Autonomo: scarica i prezzi con yfinance, calcola statistica/livelli, prova il GEX
(InsiderFinance) e scrive xau-weekly.html e spx-weekly.html. Nessuna dipendenza
dal repo app-trading. Pensato per girare anche in un ambiente cloud pulito.
"""
from __future__ import annotations
import json, math, urllib.request, datetime as dt
import numpy as np, pandas as pd, yfinance as yf

TODAY = dt.date.today()
_MESI = ["gen","feb","mar","apr","mag","giu","lug","ago","set","ott","nov","dic"]
def _itdate(d): return f"{d.day} {_MESI[d.month-1]} {d.year}"

def dl(tickers, days=400):
    df = yf.download(list(tickers), period=f"{days}d", interval="1d",
                     auto_adjust=False, progress=False)["Close"]
    if isinstance(df, pd.Series):
        df = df.to_frame()
    return df

def swings(x: pd.Series, lb=5, gap_pct=0.006):
    xr = x.reset_index(drop=True); n = len(xr); res=[]; sup=[]
    for i in range(lb, n-lb):
        w = xr[i-lb:i+lb+1]
        if xr[i] == w.max(): res.append(float(xr[i]))
        if xr[i] == w.min(): sup.append(float(xr[i]))
    def clust(v):
        v = sorted(set(round(a) for a in v)); o=[]
        g = x.iloc[-1]*gap_pct
        for a in v:
            if not o or abs(a-o[-1]) > g: o.append(a)
            else: o[-1] = (o[-1]+a)/2
        return o
    return clust(res), clust(sup)

def _ssl_ctx():
    """Il Python del Mac non ha i certificati di sistema: usa quelli di certifi."""
    import ssl
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()

def gex_levels(ticker, spot):
    """Best-effort GEX da InsiderFinance. Ritorna dict o None se non disponibile."""
    url = f"https://cf.insiderfinance.io/v1/gex?ticker={ticker}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=15, context=_ssl_ctx()).read().decode()
        obj = json.loads(raw)
        opts = obj.get("options", [])
        if not opts:
            return None
        # aggregazione grezza: call wall / put wall per OI*gamma
        agg = {}
        for o in opts:
            try:
                k = float(o["strike"]); cp = str(o.get("cp","")).upper()
                w = float(o.get("gamma",0) or 0)*float(o.get("openInterest",0) or 0)
            except Exception:
                continue
            agg.setdefault((k, cp[:1]), 0.0)
            agg[(k, cp[:1])] += w
        calls = {k:v for (k,c),v in agg.items() if c=="C"}
        puts  = {k:v for (k,c),v in agg.items() if c=="P"}
        if not calls or not puts:
            return None
        cw = max(calls, key=calls.get); pw = max(puts, key=puts.get)
        return {"call_wall": round(cw), "put_wall": round(pw)}
    except Exception:
        return None

def analyze(df, sym):
    x = df[sym].dropna()
    last = float(x.iloc[-1])
    s20, s50, s200 = (float(x.tail(n).mean()) for n in (20,50,200))
    dv = float(x.pct_change().dropna().tail(20).std()*100)
    sig_wk = dv*math.sqrt(5)/100.0
    band_lo, band_hi = last*(1-sig_wk), last*(1+sig_wk)
    hi60 = float(x.tail(60).max()); lo60 = float(x.tail(60).min())
    res, sup = swings(x)
    near = 0.08  # tieni solo livelli entro ~8% dallo spot (ladder leggibile)
    res_up = [v for v in res if last < v <= last*(1+near)][:3]
    sup_dn = [v for v in sup if last*(1-near) <= v < last][::-1][:3]
    return dict(last=last, s20=s20, s50=s50, s200=s200, dv=dv,
                band_lo=band_lo, band_hi=band_hi, hi60=hi60, lo60=lo60,
                res_up=res_up, sup_dn=sup_dn)

# ---------- rendering ----------
def fmt(v, dec=0):
    s = f"{v:,.{dec}f}".replace(",", "§").replace(".", ",").replace("§", ".")
    return s

def ladder_html(a, accent_up_is_res=True):
    spot = a["last"]
    marks = []  # (price, kind, tag)  kind: res/sup/spot/ma
    for r in a["res_up"]: marks.append((r, "res", "Resistenza"))
    for s in a["sup_dn"]: marks.append((s, "sup", "Supporto"))
    for name, val in (("SMA20", a["s20"]), ("SMA50", a["s50"]), ("SMA200", a["s200"])):
        marks.append((val, "res" if val > spot else "sup", name, True))
    prices = [m[0] for m in marks] + [spot, a["band_lo"], a["band_hi"]]
    hi = max(prices)*1.004; lo = min(prices)*0.996; span = hi-lo
    def top(p): return (hi-p)/span*100
    band = f'<div class="band" style="top:{top(a["band_hi"]):.1f}%;height:{top(a["band_lo"])-top(a["band_hi"]):.1f}%"><span class="btag">RANGE 1σ SETTIMANA</span></div>'
    rows = []
    for m in sorted(marks, key=lambda z: -z[0]):
        p, kind = m[0], m[1]; tag = m[2]; ma = len(m) > 3
        rows.append(f'<div class="lvl {kind}{" dashed" if ma else ""}" style="top:{top(p):.1f}%"><span class="px">{fmt(p)}</span><span class="line"></span><span class="tag">{tag}</span></div>')
    spot_row = f'<div class="lvl spot" style="top:{top(spot):.1f}%"><span class="px">{fmt(spot,1)}</span><span class="line"></span><span class="tag">◄ SPOT</span></div>'
    return band + "".join(rows) + spot_row

def render(a, cfg):
    up = a["last"] > a["s200"]
    badge_cls, badge = ("up", "▲ UPTREND · sopra SMA200") if up else ("down", "▼ DOWNTREND · sotto SMA200")
    d200 = (a["last"]/a["s200"]-1)*100
    gex = a.get("gex")
    if gex:
        gex_html = f'Call wall <b>{fmt(gex["call_wall"])}</b> · Put wall <b>{fmt(gex["put_wall"])}</b> (fonte InsiderFinance).'
    else:
        gex_html = 'Feed InsiderFinance <b>non disponibile</b> alla generazione (weekend/endpoint). Ricontrolla <b>/gex</b> sul bot a mercati aperti.'
    res = a["res_up"]; sup = a["sup_dn"]
    bull = " → ".join(fmt(v) for v in [a["last"]] + res[:2]) if res else fmt(a["last"])
    bear = " ↓ ".join(fmt(v) for v in ([sup[0]] + sup[1:2]) if sup) or "—"
    news = cfg["news"] if isinstance(cfg["news"], str) else "".join(cfg["news"])
    scen = f'''
    <div class="sc {'up' if up else 'range'}"><h3>{ 'Continuazione' if up else 'Rimbalzo / range' }</h3>
      <div class="trig">se {fmt(sup[0]) if sup else '—'} tiene</div><div class="path">{bull}</div></div>
    <div class="sc down"><h3>Rottura ribassista</h3>
      <div class="trig">chiusura sotto {fmt(sup[0]) if sup else '—'}</div><div class="path">{bear}</div></div>
    <div class="sc {'range' if up else 'up'}"><h3>Inversione / spinta</h3>
      <div class="trig">reclaim sopra {fmt(res[0]) if res else '—'}</div><div class="path">{" ↑ ".join(fmt(v) for v in res[:3]) if res else '—'}</div></div>'''
    week = f"{cfg['wk_start']}–{cfg['wk_end']}"
    updated = _itdate(TODAY)
    return TEMPLATE.format(
        news_note=cfg.get("news_note", ""), eyebrow=cfg.get("eyebrow", "Settimana"),
        eyebrow_long=("Settimana in corso" if cfg.get("eyebrow") == "Settimana" else "Prep settimanale"),
        title=cfg["title"], pair=cfg["pair"], ticker=cfg["ticker"], accent=cfg["accent"],
        accent_soft=cfg["accent_soft"], accent_lt=cfg["accent_lt"], accent_soft_lt=cfg["accent_soft_lt"],
        favspot_txt=cfg["spot_col_txt"], week=week, spot=fmt(a["last"],1), cur=cfg.get("cur",""),
        badge_cls=badge_cls, badge=badge,
        t_d200=("pos" if d200>=0 else "neg"), d200=f"{d200:+.1f}%".replace(".",","), s200=fmt(a["s200"]),
        band_lo=fmt(a["band_lo"]), band_hi=fmt(a["band_hi"]),
        dv=f"{a['dv']:.2f}".replace(".",","), ptmove=fmt(a["last"]*a["dv"]/100),
        fromhi=f"{(a['last']/a['hi60']-1)*100:+.1f}%".replace(".",","), hi60=fmt(a["hi60"]),
        ladder=ladder_html(a), news=news, gex_html=gex_html, driver=cfg["driver"],
        scen=scen, updated=updated)

TEMPLATE = r'''<title>{title} — {eyebrow} {week} 2026</title>
<style>
  :root{{--bg:#0a0a0b;--surface:#151516;--surface-2:#1e1e20;--border:#2c2c2f;--text:#ececea;--dim:#9a9a97;--faint:#68686a;
    --accent:{accent};--accent-soft:{accent_soft};--up:#3fa372;--up-soft:rgba(63,163,114,.14);--down:#d0554f;--down-soft:rgba(208,85,79,.14);--warn:#e0913f;
    --font-mono:ui-monospace,"SF Mono","JetBrains Mono",Menlo,Consolas,monospace;--font-sans:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;}}
  :root[data-theme="light"]{{--bg:#f6f7f9;--surface:#fff;--surface-2:#eef1f4;--border:#dde2e8;--text:#171a1f;--dim:#5f6670;--faint:#98a0ab;
    --accent:{accent_lt};--accent-soft:{accent_soft_lt};--up:#2f8a5d;--up-soft:rgba(47,138,93,.12);--down:#bd453f;--down-soft:rgba(189,69,63,.12);--warn:#b26f22;}}
  @media (prefers-color-scheme:light){{:root:not([data-theme="dark"]){{--bg:#f6f7f9;--surface:#fff;--surface-2:#eef1f4;--border:#dde2e8;--text:#171a1f;--dim:#5f6670;--faint:#98a0ab;--accent:{accent_lt};--accent-soft:{accent_soft_lt};--up:#2f8a5d;--down:#bd453f;--warn:#b26f22;}}}}
  *{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--text);font-family:var(--font-sans);line-height:1.5;-webkit-font-smoothing:antialiased;background-image:radial-gradient(120% 90% at 100% 0%,var(--accent-soft),transparent 55%)}}
  .wrap{{max-width:1180px;margin:0 auto;padding:clamp(18px,4vw,40px)}}
  .mono{{font-family:var(--font-mono);font-variant-numeric:tabular-nums}}
  .eyebrow{{font-family:var(--font-mono);font-size:12px;letter-spacing:.18em;text-transform:uppercase;color:var(--accent)}}
  .label{{font-family:var(--font-mono);font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--dim)}}
  header{{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:20px;padding-bottom:22px;border-bottom:1px solid var(--border)}}
  h1{{font-size:clamp(30px,6vw,52px);margin:.15em 0 0;letter-spacing:-.01em;font-weight:800}} h1 .pair{{color:var(--dim);font-weight:500}}
  .spotbox{{text-align:right}} .spot{{font-family:var(--font-mono);font-size:clamp(28px,5vw,44px);font-weight:700;font-variant-numeric:tabular-nums;line-height:1}} .spot .cur{{color:var(--dim);font-size:.5em;margin-right:.35em}}
  .badge{{display:inline-flex;align-items:center;gap:6px;margin-top:8px;padding:4px 10px;border-radius:999px;font-family:var(--font-mono);font-size:12px;font-weight:600;letter-spacing:.05em}}
  .badge.up{{background:var(--up-soft);color:var(--up);border:1px solid color-mix(in srgb,var(--up) 30%,transparent)}}
  .badge.down{{background:var(--down-soft);color:var(--down);border:1px solid color-mix(in srgb,var(--down) 30%,transparent)}}
  .tiles{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:22px 0}}
  .tile{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:14px 16px}}
  .tile .v{{font-family:var(--font-mono);font-size:clamp(18px,2.4vw,23px);font-weight:700;font-variant-numeric:tabular-nums;margin-top:4px}}
  .tile .sub{{font-size:12px;color:var(--dim);margin-top:2px}} .neg{{color:var(--down)}} .pos{{color:var(--up)}} .amb{{color:var(--accent)}}
  .grid{{display:grid;grid-template-columns:minmax(300px,1.05fr) 1.4fr;gap:16px;align-items:start}}
  .card{{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:18px}}
  .card h2{{font-size:13px;font-family:var(--font-mono);letter-spacing:.12em;text-transform:uppercase;color:var(--dim);margin:0 0 14px;font-weight:600;display:flex;gap:8px}} .card h2 .n{{color:var(--accent);font-weight:700}}
  .ladder{{position:relative;height:560px;margin:6px 4px 0}}
  .band{{position:absolute;left:0;right:0;background:var(--accent-soft);border-top:1px dashed color-mix(in srgb,var(--accent) 35%,transparent);border-bottom:1px dashed color-mix(in srgb,var(--accent) 35%,transparent)}}
  .band .btag{{position:absolute;right:0;top:50%;transform:translateY(-50%);font-family:var(--font-mono);font-size:10px;letter-spacing:.1em;color:var(--accent);background:var(--bg);padding:2px 6px;border-radius:6px}}
  .lvl{{position:absolute;left:0;right:0;display:flex;align-items:center;gap:8px;transform:translateY(-50%)}}
  .lvl .line{{flex:1;height:0;border-top:1.5px solid var(--l);opacity:.9}} .lvl.dashed .line{{border-top-style:dashed;opacity:.7}}
  .lvl .px{{font-family:var(--font-mono);font-size:13px;font-weight:700;font-variant-numeric:tabular-nums;color:var(--l);min-width:58px;text-align:right}}
  .lvl .tag{{font-family:var(--font-mono);font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--dim);white-space:nowrap}}
  .lvl.res{{--l:var(--down)}} .lvl.sup{{--l:var(--up)}} .lvl.spot{{--l:var(--accent);z-index:3}}
  .lvl.spot .line{{border-top-width:2px;border-top-style:solid;opacity:1}} .lvl.spot .px{{font-size:15px;background:var(--accent);color:{favspot_txt};padding:2px 8px;border-radius:6px;min-width:0}} .lvl.spot .tag{{color:var(--accent);font-weight:700}}
  .news{{display:flex;flex-direction:column;gap:2px}}
  .blackout{{display:flex;gap:10px;background:var(--surface-2);border:1px dashed var(--border);border-radius:10px;padding:10px 12px;margin-bottom:12px;font-size:13px}} .blackout b{{color:var(--warn)}}
  .ev{{display:grid;grid-template-columns:auto 1fr auto;gap:12px;align-items:center;padding:11px 0;border-bottom:1px solid var(--border)}} .ev:last-child{{border-bottom:0}}
  .ev .day{{font-family:var(--font-mono);font-size:12px;color:var(--dim);min-width:74px}} .ev .day b{{display:block;color:var(--text);font-size:13px}}
  .ev .ttl{{font-size:14px;font-weight:600}} .ev .ttl small{{display:block;font-weight:400;color:var(--dim);font-size:12px;margin-top:1px}}
  .imp{{font-family:var(--font-mono);font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;padding:3px 8px;border-radius:999px}}
  .imp.hi{{background:var(--down-soft);color:var(--down)}} .imp.md{{background:var(--accent-soft);color:var(--accent)}} .imp.lo{{background:var(--surface-2);color:var(--faint)}} .imp.wild{{background:var(--down-soft);color:var(--warn)}}
  .kv{{display:flex;justify-content:space-between;align-items:baseline;gap:10px;padding:9px 0;border-bottom:1px solid var(--border)}} .kv:last-child{{border-bottom:0}}
  .kv .k{{font-size:13px;color:var(--dim)}} .kv .v{{font-family:var(--font-mono);font-variant-numeric:tabular-nums;font-weight:600}} .kv .v small{{color:var(--dim);font-weight:400}}
  .gexnote{{font-size:13px;color:var(--dim);line-height:1.55}} .gexnote b{{color:var(--text)}}
  .scen{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:16px}}
  .sc{{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:16px;border-top:3px solid var(--edge)}}
  .sc.up{{--edge:var(--up)}} .sc.range{{--edge:var(--accent)}} .sc.down{{--edge:var(--down)}}
  .sc h3{{margin:0 0 6px;font-size:15px}} .sc .trig{{font-family:var(--font-mono);font-size:12px;color:var(--dim);margin-bottom:10px}}
  .sc .path{{font-family:var(--font-mono);font-size:13px;font-weight:700;font-variant-numeric:tabular-nums}}
  .sc.up .path{{color:var(--up)}} .sc.range .path{{color:var(--accent)}} .sc.down .path{{color:var(--down)}}
  footer{{margin-top:26px;padding-top:16px;border-top:1px solid var(--border);font-size:12px;color:var(--faint);line-height:1.6}}
  .disc{{background:var(--surface-2);border:1px solid var(--border);border-radius:10px;padding:10px 12px;margin-bottom:12px;color:var(--dim);font-size:12.5px}}
  @media (max-width:820px){{.tiles{{grid-template-columns:repeat(2,1fr)}}.grid{{grid-template-columns:1fr}}.scen{{grid-template-columns:1fr}}}}
</style>
<div class="wrap">
  <header>
    <div><div class="eyebrow">{eyebrow_long} · {week} 2026</div><h1>{title}<span class="pair"> {pair}</span></h1></div>
    <div class="spotbox"><div class="label">Spot live · {ticker}</div><div class="spot"><span class="cur">{cur}</span>{spot}</div><div class="badge {badge_cls}">{badge}</div></div>
  </header>
  <section class="tiles">
    <div class="tile"><div class="label">Prezzo vs SMA200</div><div class="v {t_d200}">{d200}</div><div class="sub">{s200} · trend lungo</div></div>
    <div class="tile"><div class="label">Range settimana 1σ</div><div class="v amb">{band_lo}–{band_hi}</div><div class="sub">~68% probabilità</div></div>
    <div class="tile"><div class="label">Volatilità giornaliera</div><div class="v">{dv}%</div><div class="sub">~{ptmove} pt/giorno</div></div>
    <div class="tile"><div class="label">Dai massimi 60g</div><div class="v neg">{fromhi}</div><div class="sub">{hi60}</div></div>
  </section>
  <div class="grid">
    <div class="card"><h2><span class="n">◆</span> Scala prezzi &amp; livelli</h2><div class="ladder">{ladder}</div></div>
    <div style="display:flex;flex-direction:column;gap:16px">
      <div class="card"><h2><span class="n">▤</span> News della settimana</h2>{news_note}
        <div class="news">{news}</div></div>
      <div class="card"><h2><span class="n">↕</span> Driver &amp; GEX</h2>{driver}
        <div class="gexnote" style="margin-top:12px"><span class="label">Opzioni / GEX</span><br>{gex_html}</div></div>
    </div>
  </div>
  <div class="scen">{scen}</div>
  <footer>
    <div class="disc">⚠️ Analisi informativa/educativa — <b>non è consulenza finanziaria</b>. Livelli e scenari sono spunti; l'esecuzione resta tua.</div>
    Rigenerata automaticamente il {updated} · dati live yfinance ({ticker}). GEX: InsiderFinance (best-effort).
  </footer>
</div>'''

def news_block(week_start, week_end):
    """Righe evento reali + nota di contesto; se il feed manca, gli appuntamenti ricorrenti."""
    try:
        from news_calendar import weekly_block
        return weekly_block(week_start, week_end, fallback=news_common())
    except Exception:
        return "".join(news_common()), (
            '<div class="blackout"><span>🔇</span><div>Calendario non raggiungibile: '
            'sotto gli appuntamenti ricorrenti.</div></div>')


def news_common():
    return [
        '<div class="ev"><div class="day">Gio</div><div class="ttl">Initial Jobless Claims<small>Lavoro USA → tassi → USD</small></div><span class="imp hi">Alto</span></div>',
        '<div class="ev"><div class="day">Ven</div><div class="ttl">PMI Flash S&amp;P Global<small>Crescita manifattura + servizi</small></div><span class="imp md">Medio</span></div>',
        '<div class="ev"><div class="day">Tutta sett.</div><div class="ttl">Geopolitica / headline rischio<small>Catalizzatore improvviso</small></div><span class="imp wild">Jolly</span></div>',
    ]

def main():
    df = dl(["GC=F", "^GSPC", "DX-Y.NYB", "^VIX", "^TNX"])
    dxy = float(df["DX-Y.NYB"].dropna().iloc[-1]); vix = float(df["^VIX"].dropna().iloc[-1]); tnx = float(df["^TNX"].dropna().iloc[-1])
    # Nei feriali la dash parla della settimana in corso; nel weekend prepara
    # quella entrante (era sempre "la prossima": di lunedì mostrava già la
    # settimana dopo, mentre i livelli sotto erano calcolati su oggi).
    if TODAY.weekday() <= 4:
        mon = TODAY - dt.timedelta(days=TODAY.weekday())
        eyebrow = "Settimana"
    else:
        mon = TODAY + dt.timedelta(days=7 - TODAY.weekday())
        eyebrow = "Prep settimanale"
    fri = mon + dt.timedelta(days=4)
    wk_start = str(mon.day); wk_end = f"{fri.day} {_MESI[fri.month-1]}"

    xau = analyze(df, "GC=F"); xau["gex"] = gex_levels("GLD", xau["last"])
    spx = analyze(df, "^GSPC"); spx["gex"] = gex_levels("SPX", spx["last"])

    _news, _note = news_block(mon, fri)
    xau_driver = f'<div class="kv"><span class="k">DXY (dollaro)</span><span class="v">{dxy:.2f} <small>corr inversa</small></span></div><div class="kv"><span class="k">US 10Y</span><span class="v">{tnx:.2f}%</span></div>'
    spx_driver = f'<div class="kv"><span class="k">VIX (paura)</span><span class="v">{vix:.2f} <small>corr inversa</small></span></div><div class="kv"><span class="k">US 10Y</span><span class="v">{tnx:.2f}%</span></div>'

    open(_XAU := "xau-weekly.html", "w").write(render(xau, dict(
        title="XAU", pair="/USD", ticker="GC=F", cur="$", accent="#c8a24b",
        accent_soft="rgba(200,162,75,.13)", accent_lt="#9d7a2b", accent_soft_lt="rgba(157,122,43,.12)",
        spot_col_txt="#0a0a0b", wk_start=wk_start, wk_end=wk_end, driver=xau_driver, news=_news, news_note=_note, eyebrow=eyebrow)))
    open(_SPX := "spx-weekly.html", "w").write(render(spx, dict(
        title="S&P 500", pair="· SPX500", ticker="^GSPC", cur="", accent="#5b93c4",
        accent_soft="rgba(91,147,196,.14)", accent_lt="#2f6ea5", accent_soft_lt="rgba(47,110,165,.11)",
        spot_col_txt="#0a0a0b", wk_start=wk_start, wk_end=wk_end, driver=spx_driver, news=_news, news_note=_note, eyebrow=eyebrow)))
    print("XAU", round(xau["last"],1), "res", xau["res_up"], "sup", xau["sup_dn"], "gex", xau["gex"])
    print("SPX", round(spx["last"],1), "res", spx["res_up"], "sup", spx["sup_dn"], "gex", spx["gex"])
    print("scritti: xau-weekly.html, spx-weekly.html")

if __name__ == "__main__":
    main()
