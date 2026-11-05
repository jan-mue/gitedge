import { HttpResponse } from "msw"
import { describe, expect, test, vi } from "vitest"
import { RepositoriesService } from "@/client"
import { createClient } from "@/client/client"
import { handleRepositoriesGetRepository } from "@/client/msw.gen"
import { server } from "@/test/server"
import { getSessionToken } from "./api-auth"

describe("browser session authentication", () => {
  test.each(["session-jwt", null])("sends only the appropriate credentials for %s", async (token) => {
    vi.mocked(localStorage.getItem).mockReturnValue(token)
    const received = vi.fn()
    server.use(
      handleRepositoriesGetRepository(({ request }) => {
        received(request.headers.get("Authorization"), request.headers.get("X-API-Key"))
        return HttpResponse.json({})
      }),
    )
    const client = createClient({ baseUrl: window.location.origin, auth: getSessionToken })

    await RepositoriesService.getRepository({ client, path: { owner: "admin", repo: "example" } })

    expect(received).toHaveBeenCalledExactlyOnceWith(token ? `Bearer ${token}` : null, null)
  })
})
