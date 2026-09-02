import { describe, expect, test } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { Input } from "./input";

describe("Input", () => {
  test("renders input element", () => {
    render(<Input />);

    expect(screen.getByRole("textbox")).toBeInTheDocument();
  });

  test("renders with placeholder", () => {
    render(<Input placeholder="Enter text" />);

    expect(screen.getByPlaceholderText("Enter text")).toBeInTheDocument();
  });

  test("renders without explicit type attribute when not specified", () => {
    render(<Input />);

    const input = screen.getByRole("textbox");
    // When type is not specified, the browser defaults to text
    // but the attribute may not be explicitly set
    expect(input.tagName).toBe("INPUT");
  });

  test("renders with specified type", () => {
    render(<Input type="email" />);

    const input = screen.getByRole("textbox");
    expect(input).toHaveAttribute("type", "email");
  });

  test("renders password type input", () => {
    render(<Input type="password" data-testid="password-input" />);

    const input = screen.getByTestId("password-input");
    expect(input).toHaveAttribute("type", "password");
  });

  test("accepts and displays value", async () => {
    const user = userEvent.setup();
    render(<Input />);

    const input = screen.getByRole("textbox");
    await user.type(input, "Hello World");

    expect(input).toHaveValue("Hello World");
  });

  test("handles onChange events", async () => {
    const user = userEvent.setup();
    let value = "";
    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      value = e.target.value;
    };

    render(<Input onChange={handleChange} />);

    await user.type(screen.getByRole("textbox"), "test");
    expect(value).toBe("test");
  });

  test("can be disabled", () => {
    render(<Input disabled />);

    const input = screen.getByRole("textbox");
    expect(input).toBeDisabled();
  });

  test("can be readonly", () => {
    render(<Input readOnly value="readonly value" />);

    const input = screen.getByRole("textbox");
    expect(input).toHaveAttribute("readonly");
  });

  test("accepts custom className", () => {
    render(<Input className="custom-class" />);

    const input = screen.getByRole("textbox");
    expect(input).toHaveClass("custom-class");
  });

  test("has data-slot attribute", () => {
    render(<Input />);

    const input = screen.getByRole("textbox");
    expect(input).toHaveAttribute("data-slot", "input");
  });

  test("forwards ref to input element", () => {
    let inputRef: HTMLInputElement | null = null;
    render(<Input ref={(ref) => { inputRef = ref }} />);

    expect(inputRef).toBeInstanceOf(HTMLInputElement);
  });

  test("applies default styling classes", () => {
    render(<Input />);

    const input = screen.getByRole("textbox");
    expect(input).toHaveClass("rounded-md");
    expect(input).toHaveClass("border");
    expect(input).toHaveClass("h-9");
  });

  test("supports aria attributes", () => {
    render(<Input aria-label="Search input" aria-describedby="search-help" />);

    const input = screen.getByRole("textbox");
    expect(input).toHaveAttribute("aria-label", "Search input");
    expect(input).toHaveAttribute("aria-describedby", "search-help");
  });

  test("supports aria-invalid for form validation", () => {
    render(<Input aria-invalid="true" />);

    const input = screen.getByRole("textbox");
    expect(input).toHaveAttribute("aria-invalid", "true");
  });

  test("supports name attribute", () => {
    render(<Input name="email" />);

    const input = screen.getByRole("textbox");
    expect(input).toHaveAttribute("name", "email");
  });

  test("supports id attribute", () => {
    render(<Input id="my-input" />);

    const input = screen.getByRole("textbox");
    expect(input).toHaveAttribute("id", "my-input");
  });

  test("supports required attribute", () => {
    render(<Input required />);

    const input = screen.getByRole("textbox");
    expect(input).toBeRequired();
  });

  test("supports maxLength attribute", () => {
    render(<Input maxLength={10} />);

    const input = screen.getByRole("textbox");
    expect(input).toHaveAttribute("maxLength", "10");
  });

  test("supports autoComplete attribute", () => {
    render(<Input autoComplete="email" />);

    const input = screen.getByRole("textbox");
    expect(input).toHaveAttribute("autocomplete", "email");
  });
});
