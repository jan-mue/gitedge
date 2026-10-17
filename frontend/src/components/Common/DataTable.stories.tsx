import type { Meta, StoryObj } from "@storybook/react-vite"
import type { ColumnDef } from "@tanstack/react-table"
import { DataTable, type DataTableFeatures } from "./DataTable"

const data = Array.from({ length: 12 }, (_, index) => ({ name: `repository-${index + 1}`, owner: "jan-mue" }))
const columns: ColumnDef<DataTableFeatures, (typeof data)[number]>[] = [
  { accessorKey: "name", header: "Repository" },
  { accessorKey: "owner", header: "Owner" },
]
const meta = { title: "Patterns/Data table" } satisfies Meta
export default meta
type Story = StoryObj
export const Pagination: Story = { render: () => <DataTable columns={columns} data={data} /> }
