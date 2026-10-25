const outdir = process.env.GITEDGE_RUNNER_BUILD_OUTDIR || "dist"

const builds: Bun.BuildConfig[] = [
  {
    entrypoints: ["src/main.ts"],
    naming: "gitedge-launch",
    target: "bun",
    // Bun's bytecode loader requires CommonJS output.
    format: "cjs",
    bytecode: true,
    minify: true,
    define: { "import.meta.main": "true" },
  },
  { entrypoints: ["prepare.ts"], naming: "prepare.mjs", target: "bun", format: "esm" },
]

for (const config of builds) {
  const result = await Bun.build({ ...config, outdir })
  if (!result.success) throw new AggregateError(result.logs, `Unable to bundle ${config.entrypoints[0]}`)
}

export {}
