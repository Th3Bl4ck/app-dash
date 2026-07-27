// Verifica la password e imposta il cookie di sessione (30 giorni).
import { createHash, timingSafeEqual } from "node:crypto";

const COOKIE = "dash_auth";
const MAX_AGE = 60 * 60 * 24 * 30;

const tokenFor = (secret) => createHash("sha256").update(`${secret}:dash-v1`).digest("hex");

export default async function handler(req, res) {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).json({ error: "method_not_allowed" });
  }

  const secret = process.env.DASH_PASSWORD;
  if (!secret) return res.status(500).json({ error: "missing_password_env" });

  const body = typeof req.body === "string" ? JSON.parse(req.body || "{}") : req.body || {};
  const given = String(body.password ?? "");

  // confronto a tempo costante su digest di lunghezza fissa
  const a = createHash("sha256").update(given).digest();
  const b = createHash("sha256").update(secret).digest();
  if (!timingSafeEqual(a, b)) return res.status(401).json({ error: "wrong_password" });

  res.setHeader(
    "Set-Cookie",
    `${COOKIE}=${tokenFor(secret)}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${MAX_AGE}`
  );
  return res.status(200).json({ ok: true });
}
