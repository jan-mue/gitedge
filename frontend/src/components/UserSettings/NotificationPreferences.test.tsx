import { HttpResponse } from "msw"
import { describe, expect, test } from "vitest"
import { handleNotificationsGetPreferences, handleNotificationsSetPreferences } from "@/client/msw.gen"
import { server } from "@/test/server"
import { render, screen, waitFor } from "@/test/test-utils"
import { NotificationPreferences } from "./NotificationPreferences"

describe("notification delivery preferences", () => {
  test("saves email opt-in and switches back to center only", async () => {
    const choices: boolean[] = []
    server.use(
      handleNotificationsGetPreferences({ body: { email: false, email_available: true } }),
      handleNotificationsSetPreferences(async ({ request }) => {
        const body = await request.json()
        choices.push(!!body.email)
        return HttpResponse.json({ ...body, email_available: true })
      }),
    )
    const { user } = render(<NotificationPreferences />)
    await user.click(await screen.findByRole("radio", { name: /Email and notification center/ }))
    await waitFor(() => expect(screen.getByRole("radio", { name: /Email and notification center/ })).toBeChecked())
    await user.click(screen.getByRole("radio", { name: /Notification center only/ }))
    await waitFor(() => expect(screen.getByRole("radio", { name: /Notification center only/ })).toBeChecked())
    expect(choices).toEqual([true, false])
  })

  test("explains unavailable email delivery", async () => {
    server.use(handleNotificationsGetPreferences({ body: { email: false, email_available: false } }))
    render(<NotificationPreferences />)
    expect(await screen.findByRole("radio", { name: /Email and notification center/ })).toBeDisabled()
    expect(screen.getByText(/administrator configures email/)).toBeInTheDocument()
  })
})
