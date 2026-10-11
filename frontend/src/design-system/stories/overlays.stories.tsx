import type { Meta, StoryObj } from "@storybook/react-vite"
import { useState } from "react"
import {
  Button,
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
  Input,
  Label,
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/design-system"

const meta = { title: "Components/Overlays", parameters: { layout: "centered" } } satisfies Meta
export default meta
type Story = StoryObj
const RepositoryDialog = ({ open = false, compact = false }: { open?: boolean; compact?: boolean }) => (
  <Dialog defaultOpen={open}>
    <DialogTrigger asChild>
      <Button>New repository</Button>
    </DialogTrigger>
    <DialogContent appearance={compact ? "compact" : undefined}>
      <DialogHeader>
        <DialogTitle>Create a repository</DialogTitle>
        <DialogDescription>Start a new project with a name and description.</DialogDescription>
      </DialogHeader>
      <div className="grid gap-3">
        <Label htmlFor="dialog-name">Repository name</Label>
        <Input id="dialog-name" placeholder="my-awesome-project" />
      </div>
      <DialogFooter>
        <DialogClose asChild>
          <Button variant="outline">Cancel</Button>
        </DialogClose>
        <Button variant="success">Create repository</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
)
export const DialogClosed: Story = { render: () => <RepositoryDialog /> }
export const DialogOpen: Story = { render: () => <RepositoryDialog open /> }
export const CompactDialog: Story = { render: () => <RepositoryDialog open compact /> }
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
const Menu = ({ open = false }: { open?: boolean }) => {
  const [watched, setWatched] = useState(true)
  return (
    <DropdownMenu defaultOpen={open}>
      <DropdownMenuTrigger asChild>
        <Button variant="outline">Repository actions</Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent appearance="account">
        <DropdownMenuLabel>jan-mue / gitedge</DropdownMenuLabel>
        <DropdownMenuItem>
          Copy URL<DropdownMenuShortcut>⌘C</DropdownMenuShortcut>
        </DropdownMenuItem>
        <DropdownMenuItem disabled>Archive repository</DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuCheckboxItem checked={watched} onCheckedChange={setWatched}>
          Watch repository
        </DropdownMenuCheckboxItem>
        <DropdownMenuRadioGroup value="main">
          <DropdownMenuRadioItem value="main">main</DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="develop">develop</DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>
        <DropdownMenuSub>
          <DropdownMenuSubTrigger>More actions</DropdownMenuSubTrigger>
          <DropdownMenuSubContent>
            <DropdownMenuItem>Create fork</DropdownMenuItem>
          </DropdownMenuSubContent>
        </DropdownMenuSub>
        <DropdownMenuSeparator />
        <DropdownMenuItem appearance="destructive">Delete repository</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
export const MenuClosed: Story = { render: () => <Menu /> }
export const MenuOpen: Story = { render: () => <Menu open /> }
export const TooltipClosed: Story = {
  render: () => (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button variant="outline">Copy URL</Button>
      </TooltipTrigger>
      <TooltipContent>Copy the HTTPS clone URL</TooltipContent>
    </Tooltip>
  ),
}
export const TooltipOpen: Story = {
  render: () => (
    <Tooltip defaultOpen>
      <TooltipTrigger asChild>
        <Button variant="outline">Copy URL</Button>
      </TooltipTrigger>
      <TooltipContent>Copy the HTTPS clone URL</TooltipContent>
    </Tooltip>
  ),
}
