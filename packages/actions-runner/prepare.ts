import { chmod, mkdir, realpath, rm, symlink } from "node:fs/promises"
import { dirname, join } from "node:path"
import { parseAction } from "./src/domain/workflow.ts"
import { writeFile } from "./src/runtime/files.ts"

async function run(command: string, ...args: string[]) {
  const child = Bun.spawn([command, ...args], { stdout: "pipe", stderr: "inherit" })
  const [code, output] = await Promise.all([child.exited, new Response(child.stdout).text()])
  if (code !== 0) throw new Error(`${command} failed with exit code ${code}`)
  return output.trim()
}

async function download(url: string, path: string) {
  const response = await fetch(url)
  if (!response.ok) throw new Error(`Download failed: ${response.status} ${url}`)
  await Bun.write(path, response)
}

async function prepareActions() {
  const root = "/opt/gitedge/actions"
  const cache = "/opt/gitedge/action-cache"
  await mkdir(cache, { recursive: true })
  const queue = (await Bun.file(new URL("./actions.txt", import.meta.url)).text()).trim().split(/\r?\n/)
  const seen = new Set<string>()
  const manifest: Record<string, string> = {}
  while (queue.length) {
    const action = queue.pop()!
    if (seen.has(action)) continue
    seen.add(action)
    if (!/^[\w.-]+\/[\w.-]+(?:\/[\w./-]+)?@[^\s]+$/.test(action)) throw new Error(`Invalid action: ${action}`)
    const [path, ref] = action.split(/@(?=[^@]*$)/)
    if (ref.startsWith("-") || path.split("/").some((part) => [".", ".."].includes(part)))
      throw new Error(`Unsafe action: ${action}`)
    const repository = path.split("/").slice(0, 2).join("/")
    const directory = join(cache, repository.replace("/", "-"))
    await run("git", "init", "--bare", directory)
    await run("git", "-C", directory, "fetch", "--depth=1", `https://github.com/${repository}.git`, ref)
    const sha = await run("git", "-C", directory, "rev-parse", "FETCH_HEAD")
    const relative = `${repository.replace("/", "-")}/${sha}`
    const tree = join(root, relative)
    await mkdir(tree, { recursive: true })
    await run("git", "--git-dir", directory, "--work-tree", tree, "checkout", "--force", sha, "--", ".")
    manifest[`${repository}@${ref}`] = relative
    const subpath = path.split("/").slice(2).join("/")
    for (const filename of ["action.yml", "action.yaml"]) {
      const metadata = Bun.file(join(tree, subpath, filename))
      if (!(await metadata.exists())) continue
      const { runs } = parseAction(await metadata.text())
      if (runs.using === "composite")
        for (const step of runs.steps) {
          if (step.kind === "action" && !step.uses.startsWith("./")) queue.push(step.uses)
        }
      break
    }
  }
  await writeFile(join(root, "manifest.json"), JSON.stringify(manifest))
  await rm(cache, { recursive: true, force: true })
}

async function prepareTools() {
  const tools = "/opt/hostedtoolcache"
  await download(
    "https://github.com/astral-sh/uv/releases/download/0.13.0/uv-x86_64-unknown-linux-gnu.tar.gz",
    "/tmp/uv.tar.gz",
  )
  await run("tar", "-xzf", "/tmp/uv.tar.gz", "-C", "/usr/local/bin", "--strip-components=1")
  await run("uv", "python", "install", "3.14.0", "--install-dir", "/opt/gitedge/python")
  const python = join(tools, "Python/3.14.0/x64")
  await run(
    "uv",
    "venv",
    python,
    "--python",
    "/opt/gitedge/python/cpython-3.14.0-linux-x86_64-gnu/bin/python3.14",
    "--seed",
    "--clear",
  )
  await run(
    "uv",
    "pip",
    "install",
    "--python",
    join(python, "bin/python"),
    "pre-commit==4.5.1",
    "codecov-cli==11.3.1",
    "coverage==7.16.2",
  )
  await writeFile(`${python}.complete`, "")
  const nodeVersion = (await run("node", "--version")).slice(1)
  const node = join(tools, "node", nodeVersion)
  await mkdir(node, { recursive: true })
  await rm(join(node, "x64"), { force: true })
  await symlink(dirname(dirname(await realpath(Bun.which("node") || "node"))), join(node, "x64"))
  await writeFile(join(node, "x64.complete"), "")
  const uv = join(tools, "uv/0.13.0/x86_64")
  await mkdir(uv, { recursive: true })
  for (const binary of ["uv", "uvx"]) {
    await rm(join(uv, binary), { force: true })
    await symlink(`/usr/local/bin/${binary}`, join(uv, binary))
  }
  await writeFile(`${uv}.complete`, "")
  await mkdir("/root/.bun/bin", { recursive: true })
  await download(
    `https://github.com/oven-sh/bun/releases/download/bun-v${Bun.version}/bun-linux-x64.zip`,
    "/tmp/bun.zip",
  )
  await run("unzip", "-qo", "/tmp/bun.zip", "-d", "/tmp/gitedge-bun")
  // Rename replaces the executable without modifying the mapped running binary.
  await run("cp", "/tmp/gitedge-bun/bun-linux-x64/bun", "/usr/local/bin/gitedge-bun-prepared")
  await run("mv", "/usr/local/bin/gitedge-bun-prepared", "/usr/local/bin/bun")
  await chmod("/usr/local/bin/bun", 0o755)
  await rm("/root/.bun/bin/bun", { force: true })
  await symlink("/usr/local/bin/bun", "/root/.bun/bin/bun")
  await rm("/tmp/bun.zip")
  await rm("/tmp/gitedge-bun", { recursive: true, force: true })
  await rm("/tmp/uv.tar.gz")
}

async function prepareCodeQL() {
  const version = "2.27.2"
  const directory = `/opt/hostedtoolcache/CodeQL/${version}/x64`
  await mkdir(directory, { recursive: true })
  await download(
    `https://github.com/github/codeql-action/releases/download/codeql-bundle-v${version}/codeql-bundle-python-linux64.tar.zst`,
    "/tmp/codeql.tar.zst",
  )
  await run("tar", "--zstd", "-xf", "/tmp/codeql.tar.zst", "-C", directory)
  await run("chmod", "-R", "a+rX", directory)
  await writeFile(`${directory}.complete`, "")
  await rm("/tmp/codeql.tar.zst")
}

if (process.argv.includes("--codeql")) await prepareCodeQL()
else if (process.argv.includes("--tools")) await prepareTools()
else {
  await prepareActions()
  await prepareTools()
  await mkdir("/gitedge", { recursive: true })
  await chmod("/usr/local/bin/gitedge-launch", 0o755)
}
