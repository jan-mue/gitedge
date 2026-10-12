import type { Meta, StoryObj } from "@storybook/react-vite"
import { useState } from "react"
import {
  Button,
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
} from "@/components/design-system"

const meta = { title: "Components/Dropdown menu" } satisfies Meta
export default meta
type Story = StoryObj
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
