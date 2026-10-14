import type { Meta, StoryObj } from "@storybook/react-vite"
import {
  Badge,
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/design-system"

const meta = { title: "Components/Table" } satisfies Meta
export default meta
type Story = StoryObj

export const RepositoryTable: Story = {
  render: () => (
    <Table>
      <TableCaption>Repositories you can access</TableCaption>
      <TableHeader>
        <TableRow appearance="static">
          <TableHead>Name</TableHead>
          <TableHead>Visibility</TableHead>
          <TableHead>Default branch</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow>
          <TableCell>jan-mue / gitedge</TableCell>
          <TableCell>
            <Badge variant="outline">Public</Badge>
          </TableCell>
          <TableCell>main</TableCell>
        </TableRow>
        <TableRow data-state="selected">
          <TableCell>jan-mue / infrastructure</TableCell>
          <TableCell>
            <Badge variant="secondary">Private</Badge>
          </TableCell>
          <TableCell>main</TableCell>
        </TableRow>
      </TableBody>
      <TableFooter>
        <TableRow>
          <TableCell colSpan={3}>2 repositories</TableCell>
        </TableRow>
      </TableFooter>
    </Table>
  ),
}
export const EmptyTable: Story = {
  render: () => (
    <Table>
      <TableHeader>
        <TableRow appearance="static">
          <TableHead>Name</TableHead>
          <TableHead>Visibility</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow appearance="static">
          <TableCell colSpan={2} appearance="empty">
            No repositories found.
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>
  ),
}
