import type { Meta, StoryObj } from "@storybook/react-vite"
import {
  Button,
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/design-system"

const meta = { title: "Components/Sheet" } satisfies Meta
export default meta
type Story = StoryObj
const NavigationSheet = ({
  open = false,
  side = "right",
}: {
  open?: boolean
  side?: "left" | "right" | "top" | "bottom"
}) => (
  <Sheet defaultOpen={open}>
    <SheetTrigger asChild>
      <Button variant="outline">Open navigation</Button>
    </SheetTrigger>
    <SheetContent side={side}>
      <SheetHeader>
        <SheetTitle>Repository navigation</SheetTitle>
        <SheetDescription>Browse code, issues, and releases.</SheetDescription>
      </SheetHeader>
      <SheetFooter>
        <SheetClose asChild>
          <Button>Close navigation</Button>
        </SheetClose>
      </SheetFooter>
    </SheetContent>
  </Sheet>
)
export const SheetClosed: Story = { render: () => <NavigationSheet /> }
export const SheetRight: Story = { render: () => <NavigationSheet open /> }
export const SheetLeft: Story = { render: () => <NavigationSheet open side="left" /> }
export const SheetTop: Story = { render: () => <NavigationSheet open side="top" /> }
export const SheetBottom: Story = { render: () => <NavigationSheet open side="bottom" /> }
