# app-dash

PWA installabile (icona in schermata Home, fullscreen, iOS + Android) con le
dashboard di trading XAU / SP500, che si rigenera da sola.

## Come funziona

    GitHub Actions (cron)  →  build.py  →  public/*.html  →  push  →  Vercel deploya

1. **GitHub Actions** esegue i generatori agli orari fissi (vedi sotto).
2. `build.py` lancia i generatori in una dir temporanea e avvolge i frammenti
   HTML in pagine complete (head PWA + barra a tab + service worker).
3. Se qualcosa è cambiato, committa `public/` e pusha.
4. **Vercel** è collegato al repo: ogni push va in produzione.

Le dipendenze pesanti (yfinance/pandas) girano su Actions, non su serverless:
niente limiti di dimensione e nessuna funzione Python da mantenere.

## Struttura
- `generators/` — copia dei generatori di `app-trading/scripts/dashboards/`.
  **Fonte di verità: app-trading.** Per risincronizzare: `make sync`.
- `build.py` — assembla `public/` dai generatori.
- `public/` — sito servito (HTML rigenerati, manifest, service worker, icone).
- `middleware.js` — gate password su tutto tranne icone, manifest e login.
- `api/login.js` — verifica la password e imposta il cookie (30 giorni).
- `tools/make_icons.py` — rigenera le icone PWA (solo se cambia la grafica).
- `.github/workflows/rigenera.yml` — il cron.

## Orari del cron (UTC nel file, qui in ora italiana estiva)
- feriali **08:00**, **15:15** (pre-apertura USA), **22:30** (post-chiusura)
- domenica **20:00** — giro per le settimanali

D'inverno scalano di un'ora (i cron GitHub sono in UTC, senza ora legale).
Si può anche lanciare a mano da GitHub → Actions → *Rigenera dashboard* → *Run workflow*.

## Scelte fatte (27/07/2026)
- **Accesso protetto da password** (env var `DASH_PASSWORD` su Vercel).
- **Tutte e tre le dash** con navigazione a tab.
- **Cron a orari fissi** (nessuna rigenerazione on-demand all'apertura).

## Setup deploy (una volta sola)
1. Crea un repo GitHub e pusha questa cartella.
2. Su Vercel: *Add New Project* → importa il repo (progetto separato da *money-tracker*).
3. Framework preset: **Other**. Output directory: `public`. Nessun build command.
4. Env var: `DASH_PASSWORD` = la password scelta (Production + Preview).
5. Apri il sito sul telefono → *Condividi* → **Aggiungi a schermata Home**.

## Sviluppo in locale

    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    python build.py                  # rigenera public/
    python3 -m http.server -d public # anteprima (senza gate password)

Il gate password e `api/login.js` girano solo su Vercel (`vercel dev` per provarli).

## Dati
- yfinance + InsiderFinance (gratis, uso personale — NON rivendibili commercialmente).
- Per una versione a pagamento servirebbero dati in licenza + inquadramento legale.
