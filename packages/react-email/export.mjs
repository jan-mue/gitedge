import { mkdir, writeFile } from "node:fs/promises"
import { createElement } from "react"
import { render } from "react-email"
import NewAccount from "./emails/new_account.tsx"
import ResetPassword from "./emails/reset_password.tsx"
import TestEmail from "./emails/test_email.tsx"

const outputDirectory = new URL("../../backend/resources/email-templates/", import.meta.url)
const templates = {
  new_account: NewAccount,
  reset_password: ResetPassword,
  test_email: TestEmail,
}

await mkdir(outputDirectory, { recursive: true })

for (const [name, Template] of Object.entries(templates)) {
  const html = await render(createElement(Template, {}))
  await writeFile(new URL(`${name}.html`, outputDirectory), `${html}\n`)
}
