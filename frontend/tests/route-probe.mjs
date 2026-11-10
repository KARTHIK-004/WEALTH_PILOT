// Drives headless Chrome over the DevTools protocol against a LOCAL dev server and prints what the page actually rendered.
// usage: node cdp_probe.mjs <url> [--auth] [--profile=<id>] [--shot=<file.png>] [--width=1280] [--mock=<json file of {pathRegex: {status, body}}>] [--wait=<regex to wait for>]
import { spawn } from "node:child_process"
import { writeFileSync, readFileSync, mkdtempSync } from "node:fs"
import { tmpdir } from "node:os"
import path from "node:path"

const args = process.argv.slice(2)
const url = args.find((a) => !a.startsWith("--"))
const flag = (name) => args.find((a) => a.startsWith(`--${name}=`))?.split("=").slice(1).join("=")
const PORT = 9400 + Math.floor(Math.random() * 300)
const profile = mkdtempSync(path.join(tmpdir(), "wp-cdp-"))
const chrome = spawn("C:/Program Files/Google/Chrome/Application/chrome.exe", ["--headless=new", `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`, "--no-first-run", "--disable-gpu", "about:blank"], { stdio: "ignore" })
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
let wsUrl
for (let i = 0; i < 60 && !wsUrl; i++) {
  try { wsUrl = (await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json()).find((t) => t.type === "page")?.webSocketDebuggerUrl } catch { await sleep(250) }
}
if (!wsUrl) { console.log("no chrome"); chrome.kill(); process.exit(2) }
const ws = new WebSocket(wsUrl)
await new Promise((r) => ws.addEventListener("open", r))
let seq = 0
const pending = new Map()
const events = []
ws.addEventListener("message", (e) => {
  const m = JSON.parse(e.data)
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id) } else events.push(m)
})
const send = (method, params = {}) => new Promise((res, rej) => { const id = ++seq; const t = setTimeout(() => rej(new Error(method + " timeout")), 40000); pending.set(id, (m) => { clearTimeout(t); res(m) }); ws.send(JSON.stringify({ id, method, params })) })
const ev = async (expression) => (await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true })).result?.result?.value

await send("Page.enable"); await send("Runtime.enable"); await send("Network.enable")
await send("Emulation.setDeviceMetricsOverride", { width: Number(flag("width") ?? 1280), height: Number(flag("height") ?? 900), deviceScaleFactor: 1, mobile: Number(flag("width") ?? 1280) < 600 })

// optional request mocking (fictional responses for API paths a real-profile page would send to the database)
const mockFile = flag("mock")
const mocks = mockFile ? Object.entries(JSON.parse(readFileSync(mockFile, "utf8"))).map(([re, v]) => [new RegExp(re), v]) : []
const mocked = []
if (mocks.length) {
  await send("Fetch.enable", { patterns: [{ urlPattern: "http://localhost:8000/*" }, { urlPattern: "http://127.0.0.1:8000/*" }] })
  ws.addEventListener("message", async (e) => {
    const m = JSON.parse(e.data)
    if (m.method !== "Fetch.requestPaused") return
    const u = new URL(m.params.request.url)
    const hit = mocks.find(([re]) => re.test(`${m.params.request.method} ${u.pathname}`))
    if (m.params.request.method === "OPTIONS") {
      await send("Fetch.fulfillRequest", { requestId: m.params.requestId, responseCode: 204, responseHeaders: [{ name: "Access-Control-Allow-Origin", value: m.params.request.headers.Origin ?? "*" }, { name: "Access-Control-Allow-Methods", value: "GET,POST,PUT,DELETE,OPTIONS" }, { name: "Access-Control-Allow-Headers", value: "*" }, { name: "Access-Control-Allow-Credentials", value: "true" }] })
      return
    }
    if (hit && hit[1].passthrough) { mocked.push(`PASS ${m.params.request.method} ${u.pathname}`); await send("Fetch.continueRequest", { requestId: m.params.requestId }); return }
    if (hit) {
      mocked.push(`${m.params.request.method} ${u.pathname}`)
      await send("Fetch.fulfillRequest", { requestId: m.params.requestId, responseCode: hit[1].status, responseHeaders: [{ name: "Content-Type", value: "application/json" }, { name: "Access-Control-Allow-Origin", value: m.params.request.headers.Origin ?? "*" }, { name: "Access-Control-Allow-Credentials", value: "true" }], body: Buffer.from(JSON.stringify(hit[1].body)).toString("base64") })
    } else {
      mocked.push(`${args.includes("--block") ? "BLOCKED" : "PASS"} ${m.params.request.method} ${u.pathname}`)
      if (args.includes("--block")) await send("Fetch.failRequest", { requestId: m.params.requestId, errorReason: "BlockedByClient" })
      else await send("Fetch.continueRequest", { requestId: m.params.requestId })
    }
  })
}

const origin = new URL(url).origin
await send("Page.navigate", { url: origin + "/login" })
await sleep(1200)
if (args.includes("--auth")) await ev(`localStorage.setItem("wealthpilot-prototype-authenticated","true")`)
if (flag("profile")) await ev(`localStorage.setItem("wealthpilot-profile-id","${flag("profile")}")`)
await send("Page.navigate", { url })
if (flag("click")) {
  const re = flag("click")
  for (let i = 0; i < 40; i++) { await sleep(400); if (await ev(`[...document.querySelectorAll("button")].some(b => new RegExp(${JSON.stringify(re)}, "i").test(b.innerText))`)) break }
  console.log("CLICKED:", await ev(`(() => { const b = [...document.querySelectorAll("button")].find(b => new RegExp(${JSON.stringify(re)}, "i").test(b.innerText)); if (!b) return null; b.click(); return b.innerText })()`))
}
const waitFor = new RegExp(flag("wait") ?? "Financial Behaviour")
for (let i = 0; i < 60; i++) {
  await sleep(500)
  const text = (await ev(`document.body.innerText`)) ?? ""
  if (waitFor.test(text) && !/Loading|Reading your|Checking/.test(text)) break
}
await sleep(1200)
for (const a of args.filter((x) => x.startsWith("--link="))) {
  const re = a.slice(7)
  const clicked = await ev(`(() => { const el = [...document.querySelectorAll("a")].find(x => new RegExp(${JSON.stringify(re)}, "i").test(x.innerText)); if (!el) return null; el.click(); return el.getAttribute("href") })()`)
  console.log("LINK CLICKED:", re, "->", clicked, "| now at", await ev(`location.pathname + location.search`).then(async () => { await sleep(1800); return await ev(`location.pathname + location.search`) }))
}
const text = (await ev(`document.body.innerText`)) ?? ""
const final = await ev(`location.pathname + location.search`)
const consoleErrors = events.filter((m) => m.method === "Runtime.exceptionThrown" || (m.method === "Runtime.consoleAPICalled" && m.params.type === "error")).map((m) => JSON.stringify(m.params).slice(0, 300))
const apiCalls = [...new Set(events.filter((m) => m.method === "Network.requestWillBeSent" && /:8000\//.test(m.params.request.url)).map((m) => `${m.params.request.method} ${new URL(m.params.request.url).pathname}`))]
console.log("FINAL URL:", final)
console.log("API CALLS:", JSON.stringify(apiCalls))
if (mocked.length) console.log("MOCK LOG:", JSON.stringify([...new Set(mocked)]))
console.log("CONSOLE ERRORS:", consoleErrors.length ? consoleErrors.join("\n") : "none")
console.log("---- RENDERED TEXT (first 2600 chars) ----")
console.log(text.slice(0, 2600))
let failed = 0
for (const a of args.filter((x) => x.startsWith("--expect="))) { const re = new RegExp(a.slice(9), "s"); const ok = re.test(text); if (!ok) failed++; console.log(`${ok ? "PASS" : "FAIL"} expect /${a.slice(9)}/`) }
for (const a of args.filter((x) => x.startsWith("--forbid="))) { const re = new RegExp(a.slice(9), "s"); const ok = !re.test(text); if (!ok) failed++; console.log(`${ok ? "PASS" : "FAIL"} forbid /${a.slice(9)}/`) }
for (const a of args.filter((x) => x.startsWith("--count="))) { const sel = a.slice(8); const n = await ev(`document.querySelectorAll(${JSON.stringify(sel)}).length`); const ok = n > 0; if (!ok) failed++; console.log(`${ok ? "PASS" : "FAIL"} dom ${sel} -> ${n}`) }
if (args.includes("--noscroll")) { const w = await ev(`[document.documentElement.scrollWidth, window.innerWidth]`); const ok = w[0] <= w[1]; if (!ok) failed++; console.log(`${ok ? "PASS" : "FAIL"} no horizontal page scroll (scrollWidth ${w[0]} <= innerWidth ${w[1]})`) }
console.log(failed ? `RESULT: ${failed} FAILED` : "RESULT: all checks passed")
if (flag("shot")) { const clip = flag("clip")?.split(",").map(Number); const shot = await send("Page.captureScreenshot", clip ? { format: "png", clip: { x: clip[0], y: clip[1], width: clip[2], height: clip[3], scale: 1 } } : { format: "png", captureBeyondViewport: true }); writeFileSync(flag("shot"), Buffer.from(shot.result.data, "base64")); console.log("screenshot:", flag("shot")) }
ws.close(); chrome.kill()
process.exit(failed ? 1 : 0)
