import { handleCompile } from "../src/handler.ts"

Bun.serve({ fetch: (request: Request) => handleCompile(request) })
