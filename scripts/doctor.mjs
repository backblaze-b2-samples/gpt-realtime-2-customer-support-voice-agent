#!/usr/bin/env node
// Preflight environment check — runs automatically before `pnpm dev`.
// Surfaces every common starter-kit setup gotcha *before* uvicorn or
// next try to start, with actionable error messages.
//
// Zero dependencies (uses only node:* core modules) so this works on a
// fresh clone before anyone has run `pnpm install`.
//
// Run directly:  node scripts/doctor.mjs
// Run via pnpm:  pnpm doctor

import { existsSync, readFileSync } from "node:fs";
import { createServer } from "node:net";
import { execSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const ENV_FILE = resolve(REPO_ROOT, ".env");
const VENV_UVICORN = resolve(REPO_ROOT, "services/api/.venv/bin/uvicorn");

// Required minimum versions. Bump as upstream support shifts.
const REQUIRED_NODE_MAJOR = 20;
const REQUIRED_PNPM_MAJOR = 9;
const REQUIRED_PYTHON_MINOR = 11; // 3.11+

// Required env vars + the exact placeholder strings shipped in
// .env.example. Keep in sync with services/api/main.py REQUIRED_B2_SETTINGS,
// REQUIRED_OPENAI_SETTINGS, and PLACEHOLDER_VALUES.
const REQUIRED_B2_VARS = [
  "B2_APPLICATION_KEY_ID",
  "B2_APPLICATION_KEY",
  "B2_BUCKET_NAME",
];
const B2_REGION_VAR = "B2_REGION";
const LEGACY_B2_ENDPOINT_VAR = "B2_ENDPOINT";
const REQUIRED_OPENAI_VARS = ["OPENAI_API_KEY"];
const REQUIRED_VARS = [...REQUIRED_B2_VARS, ...REQUIRED_OPENAI_VARS];
const B2_REGION_PATTERN = /^[a-z]{2}(?:-[a-z]+)+-[0-9]{3}$/;
const B2_ENDPOINT_PATTERN = /^https:\/\/s3\.([a-z]{2}(?:-[a-z]+)+-[0-9]{3})\.backblazeb2\.com\/?$/;
const PLACEHOLDERS = new Set([
  "your_application_key_id",
  "your_application_key",
  "your-bucket-name",
  "your-b2-region",
  "your-b2-endpoint",
  "your_openai_api_key",
]);
const RETIRED_B2_VARS = ["B2_PUBLIC_URL", "B2_KEY_ID"];

// Only Next.js: `pnpm dev` self-heals the API side via scripts/pick-port.mjs,
// so warning about 8000 here would just duplicate dev.sh's own banner.
const PORTS_TO_CHECK = [{ port: 3000, name: "Next.js dev server" }];

const failures = [];
const warnings = [];

function fail(msg, fix) {
  failures.push({ msg, fix });
}

function warn(msg, fix) {
  warnings.push({ msg, fix });
}

function tryExec(cmd) {
  try {
    return execSync(cmd, { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
  } catch {
    return null;
  }
}

function parseSemver(s) {
  // Pulls "v20.10.0" / "20.10.0" / "9.15.0" / "Python 3.13.5" — lenient.
  const match = s.match(/(\d+)\.(\d+)\.(\d+)/);
  if (!match) return null;
  return { major: +match[1], minor: +match[2], patch: +match[3] };
}

// ----- Tool versions -----

function checkNode() {
  const v = parseSemver(process.version);
  if (!v || v.major < REQUIRED_NODE_MAJOR) {
    fail(
      `Node ${process.version} is too old (need >= ${REQUIRED_NODE_MAJOR}.0.0)`,
      `Install a current Node via nvm/fnm: \`nvm install ${REQUIRED_NODE_MAJOR}\``,
    );
  }
}

function checkPnpm() {
  const out = tryExec("pnpm --version");
  if (!out) {
    fail("pnpm is not installed", "Install via corepack: `corepack enable && corepack prepare pnpm@latest --activate`");
    return;
  }
  const v = parseSemver(out);
  if (!v || v.major < REQUIRED_PNPM_MAJOR) {
    fail(
      `pnpm ${out} is too old (need >= ${REQUIRED_PNPM_MAJOR})`,
      `Run: \`corepack prepare pnpm@latest --activate\``,
    );
  }
}

function checkPython() {
  // Try python3 first (canonical on macOS/Linux), then versioned names that
  // Homebrew installs (python3.13, python3.12, python3.11), then the bare
  // python shim (Windows / pyenv). Stop at the first one that satisfies the
  // minimum version — this avoids false failures on macOS where `python3`
  // resolves to the system 3.9 even when a newer Homebrew Python is on PATH.
  const candidates = [
    "python3",
    "python3.13",
    "python3.12",
    "python3.11",
    "python",
  ];
  for (const bin of candidates) {
    const out = tryExec(`${bin} --version`);
    if (!out) continue;
    const v = parseSemver(out);
    if (v && v.major >= 3 && v.minor >= REQUIRED_PYTHON_MINOR) return; // good
  }
  // Nothing suitable found — report using the first candidate that exists.
  const found = candidates.map((b) => tryExec(`${b} --version`)).find(Boolean);
  if (found) {
    fail(
      `${found} is too old (need >= 3.${REQUIRED_PYTHON_MINOR})`,
      `Install Python 3.${REQUIRED_PYTHON_MINOR}+ via Homebrew (\`brew install python@3.12\`) or pyenv (\`pyenv install 3.${REQUIRED_PYTHON_MINOR}\`)`,
    );
  } else {
    fail(
      "Python is not on PATH",
      `Install Python 3.${REQUIRED_PYTHON_MINOR}+ from https://python.org, via Homebrew (\`brew install python@3.12\`), or pyenv`,
    );
  }
}

// ----- Project state -----

function checkVenv() {
  if (!existsSync(VENV_UVICORN)) {
    fail(
      "Backend virtualenv not set up (services/api/.venv/bin/uvicorn missing)",
      "Run: `cd services/api && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && cd ../..`",
    );
  }
}

function parseEnvFile(path) {
  // Minimal .env parser — enough for KEY=value lines, ignores comments
  // and quoted strings. We don't need the full dotenv grammar here.
  const out = {};
  const text = readFileSync(path, "utf8");
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq === -1) continue;
    const key = line.slice(0, eq).trim();
    let val = line.slice(eq + 1).trim();
    if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
      val = val.slice(1, -1);
    }
    out[key] = val;
  }
  return out;
}

function checkEnv() {
  if (!existsSync(ENV_FILE)) {
    fail(
      ".env is missing at the repo root",
      "Run: `cp .env.example .env`, then fill in your B2 credentials",
    );
    return;
  }
  const env = parseEnvFile(ENV_FILE);
  const missing = REQUIRED_VARS.filter((k) => !env[k]);
  if (!env[B2_REGION_VAR] && !env[LEGACY_B2_ENDPOINT_VAR]) {
    missing.push(`${B2_REGION_VAR} (or legacy ${LEGACY_B2_ENDPOINT_VAR})`);
  }
  if (missing.length > 0) {
    fail(
      `.env is missing required variables: ${missing.join(", ")}`,
      "See .env.example for the full list and edit .env to add them",
    );
  }
  const placeholders = [...REQUIRED_VARS, B2_REGION_VAR, LEGACY_B2_ENDPOINT_VAR].filter(
    (k) => env[k] && PLACEHOLDERS.has(env[k]),
  );
  if (placeholders.length > 0) {
    fail(
      `.env still has placeholder values: ${placeholders.join(", ")}`,
      "Edit .env and replace placeholders with your real B2 credentials (https://secure.backblaze.com/app_keys.htm?utm_source=github&utm_medium=referral&utm_campaign=ai_artifacts&utm_content=b2ai-gpt-realtime-2-customer-support-voice-agent) and your OpenAI API key (https://platform.openai.com/api-keys)",
    );
  }
  if (env[B2_REGION_VAR] && !B2_REGION_PATTERN.test(env[B2_REGION_VAR])) {
    fail(
      `${B2_REGION_VAR} must be a Backblaze region slug like <country>-<region>-<number>`,
      `Use the bucket region from the B2 dashboard, or temporarily keep ${LEGACY_B2_ENDPOINT_VAR} during migration`,
    );
  }
  if (
    env[LEGACY_B2_ENDPOINT_VAR] &&
    !B2_ENDPOINT_PATTERN.test(env[LEGACY_B2_ENDPOINT_VAR])
  ) {
    fail(
      `${LEGACY_B2_ENDPOINT_VAR} must be a Backblaze S3 endpoint like https://s3.<region>.backblazeb2.com`,
      `Prefer ${B2_REGION_VAR}; keep ${LEGACY_B2_ENDPOINT_VAR} only during a rolling migration`,
    );
  }
  if (env[LEGACY_B2_ENDPOINT_VAR]) {
    warn(
      `${LEGACY_B2_ENDPOINT_VAR} is deprecated`,
      `Set ${B2_REGION_VAR} and keep both values through one rollout before removing ${LEGACY_B2_ENDPOINT_VAR}`,
    );
  }
  const retired = RETIRED_B2_VARS.filter((k) =>
    Object.prototype.hasOwnProperty.call(env, k),
  );
  if (retired.length > 0) {
    fail(
      `.env uses retired B2 variables: ${retired.join(", ")}`,
      "Use B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY, B2_BUCKET_NAME, B2_REGION, and optional B2_PUBLIC_URL_BASE",
    );
  }
}

// ----- Network -----

// Try to bind on a single host; resolves to true if EADDRINUSE.
function isPortBoundOn(port, host) {
  return new Promise((res) => {
    const server = createServer();
    server.once("error", (err) => res(err.code === "EADDRINUSE"));
    server.once("listening", () => server.close(() => res(false)));
    server.listen(port, host);
  });
}

// We probe the wildcard interfaces (0.0.0.0 and ::) because that's what
// `next dev` and `uvicorn` actually try to bind to. Probing only the
// loopbacks misses the common case (on macOS) where a process bound to
// `::` doesn't conflict with a `127.0.0.1` probe but DOES conflict with
// `pnpm dev`'s own wildcard bind. If either wildcard is taken, the
// port is effectively unusable for the dev server.
async function checkPort({ port, name }) {
  const [v4, v6] = await Promise.all([
    isPortBoundOn(port, "0.0.0.0"),
    isPortBoundOn(port, "::"),
  ]);
  if (v4 || v6) {
    warn(
      `Port ${port} (${name}) is already in use`,
      `ok — \`pnpm dev\` will pick the next free port automatically. ` +
        `To inspect what's on it: \`lsof -nP -iTCP:${port} -sTCP:LISTEN\`.`,
    );
  }
}

// ----- Run -----

async function main() {
  checkNode();
  checkPnpm();
  checkPython();
  checkVenv();
  checkEnv();
  await Promise.all(PORTS_TO_CHECK.map(checkPort));

  if (failures.length === 0 && warnings.length === 0) {
    console.log("✓ doctor: environment looks good");
    return;
  }

  if (warnings.length > 0) {
    console.error("\n⚠  Warnings:");
    for (const { msg, fix } of warnings) {
      console.error(`  - ${msg}`);
      console.error(`    fix: ${fix}`);
    }
  }

  if (failures.length > 0) {
    console.error("\n✗ Errors:");
    for (const { msg, fix } of failures) {
      console.error(`  - ${msg}`);
      console.error(`    fix: ${fix}`);
    }
    console.error("");
    process.exit(1);
  }

  // Warnings only — non-fatal so `pnpm dev` can still proceed if the
  // user genuinely wants to (e.g. running a second instance).
  console.error("\nProceeding despite warnings.\n");
}

main();
