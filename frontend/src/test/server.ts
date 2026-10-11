import { setupServer } from "msw/node"

// Register each test's generated handlers with server.use(). Unhandled requests fail.
export const server = setupServer()
