import type { Meta, StoryObj } from "@storybook/react-vite"
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/design-system"

const meta = { title: "Components/Pagination" } satisfies Meta
export default meta
type Story = StoryObj

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
