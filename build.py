#!/usr/bin/env python3
"""Costruisce il sito PWA in public/ partendo dai generatori in generators/.

I generatori producono frammenti HTML (nati per gli artifact claude.ai): qui
vengono eseguiti in una dir temporanea e poi avvolti in pagine complete con
head PWA, barra a tab e registrazione del service worker.
"""
from __future__ import annotations
import datetime as dt, pathlib, shutil, subprocess, sys, tempfile, zoneinfo

ROOT = pathlib.Path(__file__).parent
GEN = ROOT / "generators"
PUBLIC = ROOT / "public"
TZ = zoneinfo.ZoneInfo("Europe/Rome")

# slug -> (etichetta tab, file prodotto dal generatore)
PAGES = [
    ("index.html",       "Oro · oggi",   "xau-daily.html"),
    ("xau-weekly.html",  "Oro · settimana", "xau-weekly.html"),
    ("spx-weekly.html",  "SP500 · settimana", "spx-weekly.html"),
]

HEAD = """<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<link rel="manifest" href="/manifest.webmanifest">
<meta name="theme-color" content="#0a0a0b" media="(prefers-color-scheme:dark)">
<meta name="theme-color" content="#f7f5f0" media="(prefers-color-scheme:light)">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Dash">
<link rel="apple-touch-icon" href="/icons/icon-180.png">
<link rel="icon" href="/icons/icon-192.png">
<style>
  body{padding-top:env(safe-area-inset-top)}
  .appnav{position:sticky;top:0;z-index:50;display:flex;gap:2px;padding:8px 10px;
    background:color-mix(in srgb,var(--bg,#0a0a0b) 88%,transparent);backdrop-filter:blur(12px);
    border-bottom:1px solid var(--border,#2c2c2f);overflow-x:auto;-webkit-overflow-scrolling:touch}
  .appnav a{flex:0 0 auto;padding:7px 13px;border-radius:999px;text-decoration:none;white-space:nowrap;
    font:600 12.5px/1 system-ui,-apple-system,sans-serif;color:var(--dim,#9a9a97);border:1px solid transparent}
  .appnav a[aria-current]{color:var(--accent,#c8a24b);background:var(--accent-soft,rgba(200,162,75,.13));
    border-color:color-mix(in srgb,var(--accent,#c8a24b) 30%,transparent)}
  .appnav .stamp{margin-left:auto;flex:0 0 auto;align-self:center;padding-left:10px;
    font:500 11px/1 ui-monospace,Menlo,monospace;color:var(--faint,#68686a)}
</style>
</head>
<body>
<nav class="appnav">{tabs}<span class="stamp">agg. {stamp}</span></nav>
"""

FOOT = """
<script>
if ("serviceWorker" in navigator) {
  addEventListener("load", () => navigator.serviceWorker.register("/sw.js"));
}
</script>
</body>
</html>
"""


def run_generators(workdir: pathlib.Path) -> None:
    for script in ("gen_daily_xau.py", "gen_weekly.py"):
        print(f"→ {script}")
        subprocess.run([sys.executable, str(GEN / script)], cwd=workdir, check=True)


def tabs_for(current: str) -> str:
    out = []
    for slug, label, _ in PAGES:
        cur = ' aria-current="page"' if slug == current else ""
        out.append(f'<a href="/{"" if slug == "index.html" else slug}"{cur}>{label}</a>')
    return "".join(out)


def main() -> None:
    stamp = dt.datetime.now(TZ).strftime("%d/%m %H:%M")
    with tempfile.TemporaryDirectory() as tmp:
        work = pathlib.Path(tmp)
        run_generators(work)
        PUBLIC.mkdir(exist_ok=True)
        for slug, _, produced in PAGES:
            body = (work / produced).read_text(encoding="utf-8")
            page = HEAD.replace("{tabs}", tabs_for(slug)).replace("{stamp}", stamp) + body + FOOT
            (PUBLIC / slug).write_text(page, encoding="utf-8")
            print(f"scritto: public/{slug}")


if __name__ == "__main__":
    main()
