"""Calendario macro USA per le dashboard (fonte: ForexFactory via faireconomy).

JSON pubblico, niente chiavi e niente Cloudflare davanti — a differenza
dell'endpoint di Investing.com usato dal bot, che dal 2026-07-27 risponde 403.

Autonomo di proposito (solo stdlib): i generatori devono girare anche in un
ambiente pulito, senza il package macro_engine.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import ssl
import tempfile
import time
import urllib.request
import zoneinfo

URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
TZ = zoneinfo.ZoneInfo("Europe/Rome")
_UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

# il feed limita le richieste per IP: si tiene una copia locale per mezz'ora
_CACHE = pathlib.Path(tempfile.gettempdir()) / "ff_calendar_thisweek.json"
_CACHE_TTL = 30 * 60


def _ssl_context() -> ssl.SSLContext:
    """Il Python del Mac non ha i certificati di sistema: usa quelli di certifi."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _download() -> list | None:
    if _CACHE.exists() and time.time() - _CACHE.stat().st_mtime < _CACHE_TTL:
        try:
            return json.loads(_CACHE.read_text())
        except Exception:
            pass
    try:
        req = urllib.request.Request(URL, headers=_UA)
        raw = urllib.request.urlopen(req, timeout=15, context=_ssl_context()).read().decode()
        data = json.loads(raw)
        try:
            _CACHE.write_text(raw)
        except Exception:
            pass
        return data
    except Exception:
        # rate limit o rete giù: meglio la copia vecchia che niente
        if _CACHE.exists():
            try:
                return json.loads(_CACHE.read_text())
            except Exception:
                pass
        return None

# impact ForexFactory -> (etichetta, classe css del badge)
LABELS = {"High": ("Alto", "hi"), "Medium": ("Medio", "md")}
_GIORNI = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]


def fetch(currency: str = "USD", impacts: tuple[str, ...] = ("High", "Medium")) -> list[dict] | None:
    """Eventi della settimana per valuta e livelli di impatto. None se il feed non risponde."""
    raw = _download()
    if raw is None:
        return None

    out = []
    for e in raw:
        if e.get("country") != currency or e.get("impact") not in impacts:
            continue
        try:
            when = dt.datetime.fromisoformat(e["date"]).astimezone(TZ)
        except Exception:
            continue
        out.append({
            "when": when,
            "title": (e.get("title") or "").strip(),
            "impact": e["impact"],
            "forecast": (e.get("forecast") or "").strip(),
            "previous": (e.get("previous") or "").strip(),
        })
    out.sort(key=lambda x: x["when"])
    return out


def split_today(events: list[dict], now: dt.datetime | None = None) -> tuple[list[dict], list[dict]]:
    """(eventi di oggi, prossimi eventi dei giorni successivi)."""
    now = now or dt.datetime.now(TZ)
    today = [e for e in events if e["when"].date() == now.date()]
    later = [e for e in events if e["when"].date() > now.date()]
    return today, later


def _row(e: dict, with_day: bool) -> str:
    label, css = LABELS.get(e["impact"], ("—", "lo"))
    day = f"{_GIORNI[e['when'].weekday()]} " if with_day else ""
    when = f"{day}<b>{e['when']:%H:%M}</b>"
    hint = []
    if e["forecast"]:
        hint.append(f"attesa {e['forecast']}")
    if e["previous"]:
        hint.append(f"prec. {e['previous']}")
    sub = f"<small>{' · '.join(hint)}</small>" if hint else ""
    return (f'<div class="ev"><div class="day">{when}</div>'
            f'<div class="ttl">{e["title"]}{sub}</div>'
            f'<span class="imp {css}">{label}</span></div>')


def weekly_block(week_start: dt.date, week_end: dt.date, max_items: int = 5,
                 fallback: list[str] | None = None) -> tuple[str, str]:
    """(righe evento, nota) per le dashboard settimanali.

    Il feed copre **solo la settimana in corso** (domenica→sabato). Generando la
    weekly di domenica — il suo cron — la copertura coincide con la settimana di
    preparazione: nessuna nota. Negli altri giorni mostra ciò che resta di questa
    settimana, e la nota lo dichiara per non far credere che siano gli eventi
    della settimana in testata.
    """
    warn = ('<div class="blackout"><span>🔇</span><div>{}</div></div>')
    events = fetch()
    now = dt.datetime.now(TZ)
    nexts = [e for e in (events or []) if e["when"] >= now]

    if not nexts:
        return "".join(fallback or []), warn.format(
            "Calendario non raggiungibile: sotto gli appuntamenti ricorrenti. "
            "Verifica su Investing.com / Financial Juice.")

    shown = nexts[:max_items]
    rows = "".join(_row(e, with_day=True) for e in shown)
    in_target = all(week_start <= e["when"].date() <= week_end for e in shown)
    if in_target:
        return rows, ""
    return rows, warn.format(
        "In arrivo <b>questa</b> settimana: il calendario pubblico copre solo la "
        "settimana in corso, quello della settimana in esame esce domenica.")


def daily_html(max_today: int = 6, max_next: int = 3) -> str:
    """Card 'News di oggi' del daily: eventi odierni o, se non ce ne sono, i prossimi."""
    fallback = ('<div class="blackout">Calendario non raggiungibile ora. '
                'Controlla gli eventi ad alto impatto su Investing.com / Financial Juice.</div>')
    events = fetch()
    if events is None:
        return fallback

    today, later = split_today(events)
    if today:
        return "".join(_row(e, with_day=False) for e in today[:max_today])

    rows = "".join(_row(e, with_day=True) for e in later[:max_next])
    head = ('<div class="blackout">Nessun dato USA rilevante oggi: '
            'comanda il flusso tecnico + GEX.</div>')
    return head + rows
