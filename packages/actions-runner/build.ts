for (const [entry, filename] of [
  ["launch.ts", "gitedge-launch"],
  ["prepare.ts", "prepare.mjs"],
  ["artifact-compat.ts", "artifact-compat.cjs"],
]) {
  const launcher = filename === "gitedge-launch"
  const result = await Bun.build({
    entrypoints: [entry],
    target: filename.endsWith(".cjs") ? "node" : "bun",
    format: launcher || filename.endsWith(".cjs") ? "cjs" : "esm",
    bytecode: launcher,
    minify: launcher,
    define: launcher ? { "import.meta.main": "true" } : {},
    outdir: process.env.GITEDGE_RUNNER_BUILD_OUTDIR || "dist",
    naming: filename,
  })
  if (!result.success) throw new AggregateError(result.logs, `Unable to bundle ${entry}`)
}

export {}
