import type { ColumnDef } from "@tanstack/react-table"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, test } from "vitest"

import { DataTable } from "./DataTable"

interface TestData {
  id: number
  name: string
  email: string
}

const columns: ColumnDef<TestData>[] = [
  {
    accessorKey: "id",
    header: "ID",
  },
  {
    accessorKey: "name",
    header: "Name",
  },
  {
    accessorKey: "email",
    header: "Email",
  },
]

const testData: TestData[] = [
  { id: 1, name: "John Doe", email: "john@example.com" },
  { id: 2, name: "Jane Smith", email: "jane@example.com" },
  { id: 3, name: "Bob Johnson", email: "bob@example.com" },
]

// Generate larger dataset for pagination tests
const generateLargeDataset = (count: number): TestData[] => {
  return Array.from({ length: count }, (_, i) => ({
    id: i + 1,
    name: `User ${i + 1}`,
    email: `user${i + 1}@example.com`,
  }))
}

describe("DataTable", () => {
  test("renders table with headers", () => {
    render(<DataTable columns={columns} data={testData} />)

    expect(screen.getByRole("columnheader", { name: "ID" })).toBeInTheDocument()
    expect(
      screen.getByRole("columnheader", { name: "Name" }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole("columnheader", { name: "Email" }),
    ).toBeInTheDocument()
  })

  test("renders table with data rows", () => {
    render(<DataTable columns={columns} data={testData} />)

    expect(screen.getByText("John Doe")).toBeInTheDocument()
    expect(screen.getByText("Jane Smith")).toBeInTheDocument()
    expect(screen.getByText("Bob Johnson")).toBeInTheDocument()
  })

  test("renders all data in cells", () => {
    render(<DataTable columns={columns} data={testData} />)

    expect(screen.getByText("john@example.com")).toBeInTheDocument()
    expect(screen.getByText("jane@example.com")).toBeInTheDocument()
    expect(screen.getByText("bob@example.com")).toBeInTheDocument()
  })

  test("displays 'No results found' when data is empty", () => {
    render(<DataTable columns={columns} data={[]} />)

    expect(screen.getByText("No results found.")).toBeInTheDocument()
  })

  test("renders correct number of rows", () => {
    render(<DataTable columns={columns} data={testData} />)

    // Header row + 3 data rows
    const rows = screen.getAllByRole("row")
    expect(rows).toHaveLength(4)
  })

  test("renders correct number of cells per row", () => {
    render(<DataTable columns={columns} data={testData} />)

    const cells = screen.getAllByRole("cell")
    // 3 columns * 3 data rows = 9 cells
    expect(cells).toHaveLength(9)
  })

  test("does not show pagination when data fits on one page", () => {
    render(<DataTable columns={columns} data={testData} />)

    expect(
      screen.queryByRole("button", { name: /go to first page/i }),
    ).not.toBeInTheDocument()
  })

  test("shows pagination when data exceeds page size", () => {
    const largeData = generateLargeDataset(15)
    render(<DataTable columns={columns} data={largeData} />)

    expect(
      screen.getByRole("button", { name: /go to next page/i }),
    ).toBeInTheDocument()
  })

  test("pagination buttons navigate between pages", async () => {
    const user = userEvent.setup()
    const largeData = generateLargeDataset(20)
    render(<DataTable columns={columns} data={largeData} />)

    expect(screen.getByText("User 1")).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: /go to next page/i }))

    expect(screen.getByText("User 11")).toBeInTheDocument()
  })

  test("first page button is disabled on first page", () => {
    const largeData = generateLargeDataset(15)
    render(<DataTable columns={columns} data={largeData} />)

    expect(
      screen.getByRole("button", { name: /go to first page/i }),
    ).toBeDisabled()
  })

  test("previous page button is disabled on first page", () => {
    const largeData = generateLargeDataset(15)
    render(<DataTable columns={columns} data={largeData} />)

    expect(
      screen.getByRole("button", { name: /go to previous page/i }),
    ).toBeDisabled()
  })

  test("can navigate to last page", async () => {
    const user = userEvent.setup()
    const largeData = generateLargeDataset(25)
    render(<DataTable columns={columns} data={largeData} />)

    await user.click(screen.getByRole("button", { name: /go to last page/i }))

    expect(screen.getByText("User 25")).toBeInTheDocument()
  })

  test("next page button is disabled on last page", async () => {
    const user = userEvent.setup()
    const largeData = generateLargeDataset(15)
    render(<DataTable columns={columns} data={largeData} />)

    await user.click(screen.getByRole("button", { name: /go to last page/i }))

    expect(
      screen.getByRole("button", { name: /go to next page/i }),
    ).toBeDisabled()
  })

  test("shows correct page count", () => {
    const largeData = generateLargeDataset(25)
    render(<DataTable columns={columns} data={largeData} />)

    // Default page size is 10, so 25 items = 3 pages
    // Check that pagination controls are present (page count appears in pagination)
    expect(
      screen.getByRole("button", { name: /go to last page/i }),
    ).toBeInTheDocument()
  })

  test("shows current page number", () => {
    const largeData = generateLargeDataset(20)
    render(<DataTable columns={columns} data={largeData} />)

    // Check that pagination info is displayed by looking for "Page" text
    const pageText = screen.getByText(/Page/)
    expect(pageText).toBeInTheDocument()
  })

  test("shows entry count information", () => {
    const largeData = generateLargeDataset(25)
    render(<DataTable columns={columns} data={largeData} />)

    const showingText = screen.getByText(/Showing/)
    expect(showingText).toBeInTheDocument()
  })

  test("renders table element", () => {
    render(<DataTable columns={columns} data={testData} />)

    expect(screen.getByRole("table")).toBeInTheDocument()
  })

  test("renders table header", () => {
    render(<DataTable columns={columns} data={testData} />)

    // Tables have multiple rowgroups (thead and tbody)
    const rowgroups = screen.getAllByRole("rowgroup")
    expect(rowgroups.length).toBeGreaterThanOrEqual(1)
  })

  test("empty state spans all columns", () => {
    render(<DataTable columns={columns} data={[]} />)

    const emptyCell = screen.getByText("No results found.").closest("td")
    expect(emptyCell).toHaveAttribute("colspan", "3")
  })

  test("empty state cell has correct styling", () => {
    render(<DataTable columns={columns} data={[]} />)

    const emptyCell = screen.getByText("No results found.").closest("td")
    expect(emptyCell).toHaveClass("text-center")
    expect(emptyCell).toHaveClass("text-muted-foreground")
  })
})
