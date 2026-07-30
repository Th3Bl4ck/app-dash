# app-dash

**Online: https://app-dash-gamma.vercel.app** (protetta da password) ·
repo: `Th3Bl4ck/app-dash` (pubblico — vedi nota sui cron) · progetto Vercel: `app-dash`

PWA installabile (icona in schermata Home, fullscreen, iOS + Android) con le
dashboard di trading XAU / SP500, che si rigenera da sola.

## Come funziona

    Vercel Cron  →  /api/cron  →  workflow_dispatch  →  GitHub Actions
                 →  build.py  →  public/*.html  →  push  →  Vercel deploya

1. **Vercel Cron** chiama `/api/cron` agli orari fissi, che innesca il workflow
   su GitHub via `workflow_dispatch`.
2. `build.py` lancia i generatori in una dir temporanea e avvolge i frammenti
   HTML in pagine complete (head PWA + barra a tab + service worker).
3. Se qualcosa è cambiato, committa `public/` e pusha.
4. **Vercel** è collegato al repo: ogni push va in produzione.

Le dipendenze pesanti (yfinance/pandas) girano su Actions, non su serverless:
niente limiti di dimensione e nessuna funzione Python da mantenere.

**Perché l'innesco arriva da Vercel e non dal cron di Actions:** lo scheduler di
GitHub non è puntuale. Misurato dal 27 al 29/07/2026: il giro del mattino
(~06:00 UTC, la fascia più congestionata) è stato **scartato tutte le volte**,
gli altri due sono partiti con **1-2 ore di ritardo**. Rendere il repo pubblico
non ha cambiato nulla. Un `workflow_dispatch`, invece, parte in pochi secondi:
serve solo un cron puntuale che lo chiami. I cron di Actions restano attivi come
rete di sicurezza (in ritardo, ma coprono un'eventuale caduta di Vercel).

## Struttura
- `generators/` — copia dei generatori di `app-trading/scripts/dashboards/`.
  **Fonte di verità: app-trading.** Per risincronizzare: `make sync`.
- `build.py` — assembla `public/` dai generatori.
- `public/` — sito servito (HTML rigenerati, manifest, service worker, icone).
- `middleware.js` — gate password su tutto tranne icone, manifest e login.
- `api/login.js` — verifica la password e imposta il cookie (30 giorni).
- `tools/make_icons.py` — rigenera le icone PWA (solo se cambia la grafica).
- `api/cron.js` — innesca il workflow su GitHub (chiamato dal cron di Vercel).
- `.github/workflows/rigenera.yml` — il workflow che rigenera (+ cron di scorta).

## Orari del cron (UTC nei file, qui in ora italiana estiva)
Definiti in `vercel.json` (primari) e in `rigenera.yml` (scorta, un minuto prima):
- feriali **07:58**, **15:13** (pre-apertura USA), **22:28** (post-chiusura)
- domenica **21:58** — giro per le settimanali

Minuti sparsi di proposito (agli orari tondi la coda GitHub è più lunga).
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
4. Env var (Production + Preview):
   - `DASH_PASSWORD` = la password per entrare
   - `GH_DISPATCH_TOKEN` = token GitHub fine-grained, solo questo repo,
     permesso *Actions: read and write* (serve a innescare il workflow)
   - `CRON_SECRET` = stringa casuale lunga; Vercel la usa per firmare le
     chiamate al cron, così nessun altro può innescare i giri
5. Apri il sito sul telefono → *Condividi* → **Aggiungi a schermata Home**.

Il `GH_DISPATCH_TOKEN` ha una scadenza: quando scade i giri automatici si
fermano silenziosamente. Vale la pena segnarsi la data.

## Sviluppo in locale

    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    python build.py                  # rigenera public/
    python3 -m http.server -d public # anteprima (senza gate password)

Il gate password e `api/login.js` girano solo su Vercel (`vercel dev` per provarli).

## Dati
- yfinance + InsiderFinance (gratis, uso personale — NON rivendibili commercialmente).
- Per una versione a pagamento servirebbero dati in licenza + inquadramento legale.
