for (const [entry, filename] of [
  ["launch.ts", "gitedge-launch"],
  ["prepare.ts", "prepare.mjs"],
  ["artifact-compat.ts", "artifact-compat.cjs"],
]) {
  const result = await Bun.build({
    entrypoints: [entry],
    target: filename.endsWith(".cjs") ? "node" : "bun",
    format: filename.endsWith(".cjs") ? "cjs" : "esm",
    outdir: "dist",
    naming: filename,
  })
  if (!result.success) throw new AggregateError(result.logs, `Unable to bundle ${entry}`)
}

export {}
