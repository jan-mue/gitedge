for (const [entry, filename] of [
  ["launch.mjs", "gitedge-launch"],
  ["prepare.mjs", "prepare.mjs"],
]) {
  const result = await Bun.build({ entrypoints: [entry], target: "bun", outdir: "dist", naming: filename })
  if (!result.success) throw new AggregateError(result.logs, `Unable to bundle ${entry}`)
}
