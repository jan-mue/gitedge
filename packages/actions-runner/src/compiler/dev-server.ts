import { handleCompile } from "./handler.ts"

if (!Bun.env.COMPILER_TOKEN) throw new Error("COMPILER_TOKEN must be configured")
const server = Bun.serve({
  hostname: "127.0.0.1",
  port: Number(Bun.env.COMPILER_PORT || 8765),
  fetch: handleCompile,
  maxRequestBodySize: 2 * 1024 * 1024,
})
console.log(`GITEDGE_COMPILER_READY ${server.port}`)
for (const signal of ["SIGINT", "SIGTERM"] as const)
  process.on(signal, () => {
    server.stop(true)
    process.exit(0)
  })
