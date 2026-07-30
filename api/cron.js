// Innesca il workflow di rigenerazione su GitHub.
//
// Perché passare da qui invece di usare il cron di GitHub Actions: lo scheduler
// di Actions scarta il giro del mattino e ritarda gli altri di 1-2 ore
// (misurato 27-29/07/2026). Un workflow_dispatch, invece, parte in pochi
// secondi — serve solo qualcuno di puntuale che lo chiami, e quello è il cron
// di Vercel.
const REPO = "Th3Bl4ck/app-dash";
const WORKFLOW = "rigenera.yml";

export default async function handler(req, res) {
  // Vercel Cron firma le sue chiamate con CRON_SECRET: senza quell'header
  // l'endpoint non deve fare nulla, altrimenti chiunque potrebbe innescarlo.
  const secret = process.env.CRON_SECRET;
  if (secret && req.headers.authorization !== `Bearer ${secret}`) {
    return res.status(401).json({ error: "unauthorized" });
  }

  const token = process.env.GH_DISPATCH_TOKEN;
  if (!token) return res.status(500).json({ error: "missing_gh_dispatch_token" });

  const r = await fetch(
    `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ ref: "main" }),
    }
  );

  // 204 = accettato, nessun corpo di risposta
  if (r.status === 204) return res.status(200).json({ ok: true, dispatched: true });

  const detail = await r.text();
  console.error(`dispatch fallito: ${r.status} ${detail}`);
  return res.status(502).json({ error: "dispatch_failed", status: r.status, detail });
}
