// Runs the component cases (tests/*-view.cases.tsx: behaviour & sentiment, data protection) under Node's built-in test runner.
//
// The cases are TSX that imports the app through the "@/" alias, so they are loaded with Vite's SSR loader (Vite is already a dependency; no browser, no jsdom, no new package). The Vite
// server runs in middleware mode: it opens no port and serves nothing. Each case is registered as an ordinary node:test test.
import { after, test } from "node:test"
import { fileURLToPath } from "node:url"

import { createServer } from "vite"

const root = fileURLToPath(new URL("..", import.meta.url))
process.chdir(root) // the cases read tests/fixtures relative to the frontend folder

// tests/mutation-check.mjs sets WP_MUTATION to apply ONE in-memory source mutation (nothing on disk changes) and expects at least one case to fail.
const mutation = process.env.WP_MUTATION ? JSON.parse(process.env.WP_MUTATION) : null
let mutationApplied = false
const mutationPlugin = {
  name: "wp-mutation",
  enforce: "pre",
  transform(code, id) {
    if (!mutation || !id.replaceAll("\\", "/").endsWith(mutation.file)) return null
    const text = code.replace(/\r\n/g, "\n") // a multi-line target must match a CRLF file; a missing target is reported as "not applied" (exit 3), never thrown as a fake test failure
    if (!text.includes(mutation.find)) return null
    mutationApplied = true
    return text.split(mutation.find).join(mutation.replace)
  },
}

const server = await createServer({
  root,
  plugins: [mutationPlugin],
  appType: "custom",
  logLevel: "error",
  server: { middlewareMode: true, hmr: false, watch: null },
  optimizeDeps: { noDiscovery: true, include: [] },
})
after(async () => {
  await server.close()
  if (mutation && !mutationApplied) {
    console.error("MUTATION NOT APPLIED")
    process.exitCode = 3
  }
})

// Every module is loaded BEFORE any test is registered: a test starts running as soon as it is registered, and the `after` hook above closes the server when they finish.
const loaded = []
for (const file of ["behaviour-sentiment-view.cases.tsx", "security-status-view.cases.tsx", "demo-financial-behaviour-view.cases.tsx", "behaviour-page.cases.tsx", "demo-reachability.cases.tsx", "transformer-research.cases.tsx"]) loaded.push(await server.ssrLoadModule(`/tests/${file}`))
for (const { cases } of loaded) for (const [name, run] of Object.entries(cases)) test(name, run)
