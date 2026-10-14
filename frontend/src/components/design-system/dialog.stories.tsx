import type { Meta, StoryObj } from "@storybook/react-vite"
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
  Input,
  Label,
} from "@/components/design-system"

const meta = { title: "Components/Dialog" } satisfies Meta
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
