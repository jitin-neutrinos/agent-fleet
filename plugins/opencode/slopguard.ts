// slopguard — deterministic anti-slop enforcement for opencode.
// Blocks secret-bearing file writes (env files exempt) and package installs of
// packages that do not exist in npm/PyPI (slopsquatting). Fail-open on network
// errors. Installed 2026-09-30; safe to delete.
const SECRETS: Array<[RegExp, string]> = [
  [/AKIA[0-9A-Z]{16}/, "AWS access key id"],
  [/(aws)?_?secret_?access_?key\s*[:=]\s*['"][A-Za-z0-9/+=]{32,}['"]/i, "AWS secret access key"],
  [/-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----/, "private key block"],
  [/\bgh[pousr]_[A-Za-z0-9]{36,}/, "GitHub token"],
  [/\bxox[baprs]-[A-Za-z0-9-]{10,}/, "Slack token"],
  [/\b(api_?key|secret|token|passwd|password)\b\s*[:=]\s*['"][A-Za-z0-9+/_-]{24,}['"]/i, "hardcoded credential"],
]
const PLACEHOLDER = /(?:\b|')(x{3,}|example|placeholder|changeme|dummy|your[-_][a-z]*|<[^>]+>)(?:\b|')/i
const ENVPATH = /\.env(\.|$)|\/secrets?\//i

const regCache = new Map<string, boolean | null>()
async function pkgExists(registry: string, name: string): Promise<boolean | null> {
  const key = registry + ":" + name
  if (regCache.has(key)) return regCache.get(key)!
  const url = registry === "npm"
    ? "https://registry.npmjs.org/" + name
    : "https://pypi.org/pypi/" + name + "/json"
  let ok: boolean | null
  try {
    const r = await fetch(url)
    ok = r.status === 200
  } catch (e: any) {
    ok = e?.status === 404 ? false : null
  }
  regCache.set(key, ok)
  return ok
}

const SEP = "[\\s'\"\\[\\],()]"
const NPM_RE = new RegExp("\\b(?:npm|i|yarn|pnpm)(?:" + SEP + "+add|" + SEP + "+install|" + SEP + "+i)" + SEP + "+([^&|;]+)|\\bnpx" + SEP + "+-?y?" + SEP + "+(@?[\\w@/.-]+)")
const PY_RE = new RegExp("\\b(?:pip3?|uv)(?:" + SEP + "+pip)?" + SEP + "+install" + SEP + "+([^&|;\\]]+)|\\buv" + SEP + "+add" + SEP + "+([^&|;\\]]+)")
const PKG = /^(@?[\w][\w.-]*).*$/

async function fakePackage(command: string): Promise<string | null> {
  const targets: Array<[string, string]> = []
  const nm = NPM_RE.exec(command)
  if (nm) {
    if (nm[2]) targets.push(["npm", nm[2]])
    else for (const raw of (nm[1] || "").split(/\s+/)) {
      if (raw.startsWith("-")) continue
      const p = PKG.exec(raw.replace(/^["'-,]+|["',-]+$/g, ""))
      if (p) targets.push(["npm", p[1]])
    }
  }
  const pm = PY_RE.exec(command)
  if (pm) {
    for (const raw of ((pm[1] || pm[2] || "")).split(/\s+/)) {
      if (raw.startsWith("-")) continue
      const p = PKG.exec(raw.replace(/^["',-]+|["',-]+$/g, ""))
      if (p) {
        const base = p[1].split(/[\[=<>!~;]/)[0]
        if (base) targets.push(["pypi", base])
      }
    }
  }
  for (const [registry, name] of targets) {
    const ok = await pkgExists(registry, name.replace(/\/+$/, ""))
    if (ok === false) return name
  }
  return null
}

export const SlopguardPlugin = async () => ({
  "tool.execute.before": async (input: any, output: any) => {
    try {
      const tool = String(input?.tool ?? "").toLowerCase()
      const args = output?.args ?? {}
      const command = String(args.command ?? args.script ?? args.code ?? "")
      if (command.trim()) {
        const bad = await fakePackage(command)
        if (bad) {
          throw new Error(
            `slopguard: package '${bad}' does not exist in its registry — hallucinated packages are an attack vector (slopsquatting). Check the real package name and retry.`)
        }
      }
      const path = String(args.path ?? args.file_path ?? "")
      const content = String(args.content ?? args.new_string ?? "")
      if (path && content && !ENVPATH.test(path)) {
        for (const [pat, reason] of SECRETS) {
          const hit = pat.exec(path + "\n" + content)
          if (hit && !PLACEHOLDER.test(hit[0])) {
            throw new Error(
              `slopguard: ${reason} in plaintext write to ${path}. Move it to an environment file (.env / secrets dir) and reference it by name.`)
          }
        }
      }
    } catch (e: any) {
      if (e?.message?.startsWith("slopguard:")) throw e
      // internal error → fail open
    }
  },
})
