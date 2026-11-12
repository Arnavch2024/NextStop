const { spawnSync } = require("child_process");
const path = require("path");

const url =
  process.argv[2] ||
  "https://characteristics-minds-compute-friends.trycloudflare.com";

console.log(`[Discovery] Publishing backend URL to Supabase Cloud registry: ${url}`);

const pythonScript = path.join(__dirname, "..", "apps", "api", "scripts", "publish_backend_url.py");
const pythonBin = process.platform === "win32"
  ? path.join(__dirname, "..", "apps", "api", ".venv", "Scripts", "python.exe")
  : path.join(__dirname, "..", "apps", "api", ".venv", "bin", "python");

const result = spawnSync(`"${pythonBin}"`, [`"${pythonScript}"`, `"${url}"`], {
  stdio: "inherit",
  shell: true,
});

if (result.status === 0) {
  console.log(`[Discovery] Success! All mobile apps will now automatically connect to: ${url}`);
} else {
  console.error(`[Discovery] Failed to publish URL (exit code ${result.status})`);
  process.exit(1);
}
