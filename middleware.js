// Gate password: tutto è protetto tranne login, icone e manifest
// (questi ultimi devono restare leggibili perché la PWA sia installabile).
export const config = {
  matcher: "/((?!icons/|manifest.webmanifest|login|api/login).*)",
};

const COOKIE = "dash_auth";

async function expectedToken() {
  const secret = process.env.DASH_PASSWORD;
  if (!secret) return null;
  const bytes = new TextEncoder().encode(`${secret}:dash-v1`);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export default async function middleware(request) {
  const token = await expectedToken();
  if (!token) {
    return new Response(
      "Configurazione incompleta: manca la variabile d'ambiente DASH_PASSWORD.",
      { status: 500, headers: { "content-type": "text/plain; charset=utf-8" } }
    );
  }

  const cookie = request.headers
    .get("cookie")
    ?.split(";")
    .map((c) => c.trim())
    .find((c) => c.startsWith(`${COOKIE}=`))
    ?.slice(COOKIE.length + 1);

  if (cookie === token) return;

  const url = new URL(request.url);
  const next = encodeURIComponent(url.pathname + url.search);
  return Response.redirect(new URL(`/login?next=${next}`, url), 302);
}
