import { screen } from "@testing-library/react"
import { expect, test } from "vitest"
import { render } from "@/test/test-utils"
import { StoryRouter } from "./StoryRouter"

test("updates story content when controls change", async () => {
  const { rerender } = render(
    <StoryRouter>
      <p>Original repository</p>
    </StoryRouter>,
  )
  expect(await screen.findByText("Original repository")).toBeInTheDocument()
  rerender(
    <StoryRouter>
      <p>Updated repository</p>
    </StoryRouter>,
  )
  expect(await screen.findByText("Updated repository")).toBeInTheDocument()
  expect(screen.queryByText("Original repository")).not.toBeInTheDocument()
})
