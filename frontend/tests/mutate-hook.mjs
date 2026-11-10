// Applies ONE in-memory source mutation to the code under test, for tests/mutation-check.mjs. Nothing on disk is ever modified.
//
// Used as `node --import ./tests/mutate-hook.mjs --test ...` with WP_MUTATION='{"file":"src/lib/user-text-input.ts","find":"...","replace":"..."}'. Two paths are covered:
//   - a module that is IMPORTED (a load hook rewrites its source before it runs), and
//   - a file the tests READ AS TEXT with readFileSync (the privacy and wiring checks scan the card, hook, API client and page sources).
// If the target text is not found, or the file is never touched, the run exits with code 3 so a stale mutation can never be mistaken for a surviving or a killed one.
import fs from "node:fs"
import { registerHooks, syncBuiltinESMExports } from "node:module"
import { fileURLToPath } from "node:url"

const spec = process.env.WP_MUTATION ? JSON.parse(process.env.WP_MUTATION) : null

if (spec) {
  let applied = false
  // Line endings are normalised so a multi-line target matches a CRLF file. A target that is not found is NOT thrown (a throw is indistinguishable from a failing test, so a stale
  // mutation would be counted as killed): the source is left unchanged and the run ends with exit code 3, "not applied".
  const mutate = (source) => {
    const text = source.replace(/\r\n/g, "\n")
    if (!text.includes(spec.find)) return source
    applied = true
    return text.split(spec.find).join(spec.replace)
  }

  registerHooks({
    load(url, context, nextLoad) {
      const result = nextLoad(url, context)
      if (url.replaceAll("\\", "/").endsWith(spec.file)) result.source = mutate(String(result.source))
      return result
    },
  })

  const realReadFileSync = fs.readFileSync
  fs.readFileSync = function (target, ...rest) {
    const content = realReadFileSync.call(this, target, ...rest)
    const asPath = typeof target === "string" ? target : target instanceof URL ? fileURLToPath(target) : ""
    if (typeof content === "string" && asPath.replaceAll("\\", "/").endsWith(spec.file)) return mutate(content)
    return content
  }
  syncBuiltinESMExports() // the tests use the named import { readFileSync } from "node:fs"

  process.on("exit", () => {
    if (!applied) {
      console.error("MUTATION NOT APPLIED")
      process.exitCode = 3
    }
  })
}
