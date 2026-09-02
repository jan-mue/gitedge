import { describe, expect, test } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { PasswordInput } from "./password-input"

describe("PasswordInput", () => {
  test("renders password input element", () => {
    render(<PasswordInput data-testid="password" />)

    expect(screen.getByTestId("password")).toBeInTheDocument()
  })

  test("input type is password by default", () => {
    render(<PasswordInput data-testid="password" />)

    expect(screen.getByTestId("password")).toHaveAttribute("type", "password")
  })

  test("renders with placeholder", () => {
    render(<PasswordInput placeholder="Enter password" />)

    expect(screen.getByPlaceholderText("Enter password")).toBeInTheDocument()
  })

  test("toggles password visibility when clicking the toggle button", async () => {
    const user = userEvent.setup()
    render(<PasswordInput data-testid="password" />)

    const input = screen.getByTestId("password")
    const toggleButton = screen.getByRole("button", { name: /show password/i })

    expect(input).toHaveAttribute("type", "password")

    await user.click(toggleButton)
    expect(input).toHaveAttribute("type", "text")

    await user.click(screen.getByRole("button", { name: /hide password/i }))
    expect(input).toHaveAttribute("type", "password")
  })

  test("shows eye icon when password is hidden", () => {
    render(<PasswordInput data-testid="password" />)

    expect(
      screen.getByRole("button", { name: /show password/i })
    ).toBeInTheDocument()
  })

  test("shows eye-off icon when password is visible", async () => {
    const user = userEvent.setup()
    render(<PasswordInput data-testid="password" />)

    await user.click(screen.getByRole("button", { name: /show password/i }))

    expect(
      screen.getByRole("button", { name: /hide password/i })
    ).toBeInTheDocument()
  })

  test("accepts and displays value", async () => {
    const user = userEvent.setup()
    render(<PasswordInput data-testid="password" />)

    const input = screen.getByTestId("password")
    await user.type(input, "secret123")

    expect(input).toHaveValue("secret123")
  })

  test("handles onChange events", async () => {
    const user = userEvent.setup()
    let value = ""
    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      value = e.target.value
    }

    render(<PasswordInput data-testid="password" onChange={handleChange} />)

    await user.type(screen.getByTestId("password"), "mypassword")
    expect(value).toBe("mypassword")
  })

  test("can be disabled", () => {
    render(<PasswordInput data-testid="password" disabled />)

    expect(screen.getByTestId("password")).toBeDisabled()
  })

  test("accepts custom className", () => {
    render(<PasswordInput data-testid="password" className="custom-class" />)

    expect(screen.getByTestId("password")).toHaveClass("custom-class")
  })

  test("has data-slot attribute", () => {
    render(<PasswordInput data-testid="password" />)

    expect(screen.getByTestId("password")).toHaveAttribute("data-slot", "input")
  })

  test("forwards ref to input element", () => {
    let inputRef: HTMLInputElement | null = null
    render(<PasswordInput ref={(ref) => { inputRef = ref }} />)

    expect(inputRef).toBeInstanceOf(HTMLInputElement)
  })

  test("applies default styling classes", () => {
    render(<PasswordInput data-testid="password" />)

    const input = screen.getByTestId("password")
    expect(input).toHaveClass("rounded-md")
    expect(input).toHaveClass("border")
    expect(input).toHaveClass("h-9")
  })

  test("has aria-invalid when error is provided", () => {
    render(<PasswordInput data-testid="password" error="Invalid password" />)

    expect(screen.getByTestId("password")).toHaveAttribute(
      "aria-invalid",
      "true"
    )
  })

  test("toggle button does not submit form", async () => {
    const user = userEvent.setup()
    let formSubmitted = false
    const handleSubmit = (e: React.FormEvent) => {
      e.preventDefault()
      formSubmitted = true
    }

    render(
      <form onSubmit={handleSubmit}>
        <PasswordInput data-testid="password" />
      </form>
    )

    await user.click(screen.getByRole("button", { name: /show password/i }))
    expect(formSubmitted).toBe(false)
  })

  test("toggle button has ghost variant styling", () => {
    render(<PasswordInput data-testid="password" />)

    const toggleButton = screen.getByRole("button", { name: /show password/i })
    expect(toggleButton).toHaveClass("hover:bg-transparent")
  })

  test("supports name attribute", () => {
    render(<PasswordInput data-testid="password" name="user-password" />)

    expect(screen.getByTestId("password")).toHaveAttribute(
      "name",
      "user-password"
    )
  })

  test("supports id attribute", () => {
    render(<PasswordInput data-testid="password" id="my-password" />)

    expect(screen.getByTestId("password")).toHaveAttribute("id", "my-password")
  })

  test("supports required attribute", () => {
    render(<PasswordInput data-testid="password" required />)

    expect(screen.getByTestId("password")).toBeRequired()
  })

  test("supports autoComplete attribute", () => {
    render(
      <PasswordInput data-testid="password" autoComplete="current-password" />
    )

    expect(screen.getByTestId("password")).toHaveAttribute(
      "autocomplete",
      "current-password"
    )
  })
})
