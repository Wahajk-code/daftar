// A look at a running dev server from the inside, without a browser: `node scripts/smoke.mjs <email> [paths...]`.
// It signs in through the BFF with the demonstration password, then fetches pages (HTML) and API paths (JSON) as that person
// and prints the status of each, so a contract mismatch between the screens and the API shows up before anyone clicks.
const base = process.env.SMOKE_BASE ?? "http://localhost:3000";
const email = process.argv[2] ?? "admin@daftar.pk";
const password = process.env.SMOKE_PASSWORD ?? "daftar-demo-2026";

const login = await fetch(`${base}/api/auth/login`, {
  method: "POST",
  headers: { "Content-Type": "application/json", Origin: base },
  body: JSON.stringify({ email, password }),
  redirect: "manual",
});
console.log(`login ${email}`, login.status);
const setCookies = login.headers.getSetCookie();
for (const cookie of setCookies) {
  if (!/HttpOnly/i.test(cookie)) console.log("  NOT HttpOnly:", cookie.split("=")[0]);
}
const jar = setCookies.map((cookie) => cookie.split(";")[0]).join("; ");

for (const path of process.argv.slice(3)) {
  const response = await fetch(`${base}${path}`, { headers: { Cookie: jar, Accept: "application/json" }, redirect: "manual" });
  const type = response.headers.get("content-type") ?? "";
  let note = "";
  if (type.includes("json")) {
    const body = await response.json();
    note = Array.isArray(body) ? `${body.length} items` : body.items ? `${body.items.length} of ${body.total}` : (body.code ?? "").toString();
    if (!response.ok) note += ` ${body.detail ?? ""}`;
  } else {
    const text = await response.text();
    note = `${/<title>([^<]*)<\/title>/.exec(text)?.[1] ?? ""} ${response.headers.get("location") ?? ""} ${text.length} bytes`;
  }
  console.log(String(response.status).padEnd(4), path, "->", note.trim());
}
