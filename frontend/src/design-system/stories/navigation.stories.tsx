import type { Meta, StoryObj } from "@storybook/react-vite"
import {
  Badge,
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/design-system"

const meta = { title: "Components/Navigation and data" } satisfies Meta
export default meta
type Story = StoryObj
export const TabNavigation: Story = {
  render: () => (
    <Tabs defaultValue="code" appearance="spaced">
      <TabsList>
        <TabsTrigger value="code">Code</TabsTrigger>
        <TabsTrigger value="issues">Issues</TabsTrigger>
        <TabsTrigger value="actions" disabled>
          Actions
        </TabsTrigger>
      </TabsList>
      <TabsContent value="code">Browse your repository files.</TabsContent>
      <TabsContent value="issues">Track bugs and feature requests.</TabsContent>
    </Tabs>
  ),
}
const BranchSelect = ({ open = false, disabled = false }: { open?: boolean; disabled?: boolean }) => (
  <Select defaultValue="main" defaultOpen={open} disabled={disabled}>
    <SelectTrigger aria-label="Branch">
      <SelectValue placeholder="Select a branch" />
    </SelectTrigger>
    <SelectContent>
      <SelectGroup>
        <SelectLabel>Branches</SelectLabel>
        <SelectItem value="main">main</SelectItem>
        <SelectItem value="develop">develop</SelectItem>
        <SelectItem value="archived" disabled>
          archived
        </SelectItem>
      </SelectGroup>
      <SelectSeparator />
      <SelectGroup>
        <SelectLabel>Tags</SelectLabel>
        <SelectItem value="v1">v1.0.0</SelectItem>
      </SelectGroup>
    </SelectContent>
  </Select>
)
export const SelectClosed: Story = { render: () => <BranchSelect /> }
export const SelectOpen: Story = { render: () => <BranchSelect open /> }
export const SelectDisabled: Story = { render: () => <BranchSelect disabled /> }
export const PaginationControl: Story = {
  render: () => (
    <Pagination aria-label="Repository pages">
      <PaginationContent>
        <PaginationItem>
          <PaginationPrevious href="#previous" />
        </PaginationItem>
        <PaginationItem>
          <PaginationLink href="#one" isActive>
            1
          </PaginationLink>
        </PaginationItem>
        <PaginationItem>
          <PaginationLink href="#two">2</PaginationLink>
        </PaginationItem>
        <PaginationItem>
          <PaginationEllipsis />
        </PaginationItem>
        <PaginationItem>
          <PaginationNext href="#next" />
        </PaginationItem>
      </PaginationContent>
    </Pagination>
  ),
}
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
