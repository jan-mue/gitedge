import { handleCompile } from "../src/handler"

export default { fetch: (request: Request) => handleCompile(request) }
