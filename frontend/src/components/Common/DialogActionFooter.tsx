import { Button, DialogClose, DialogFooter, LoadingButton } from "@/components/design-system"

export const DialogActionFooter = ({ pending, destructive = false }: { pending: boolean; destructive?: boolean }) => {
  return (
    <DialogFooter appearance={destructive ? "spaced" : undefined}>
      <DialogClose asChild>
        <Button variant="repository" disabled={pending}>
          Cancel
        </Button>
      </DialogClose>
      <LoadingButton variant={destructive ? "destructive" : undefined} type="submit" loading={pending}>
        {destructive ? "Delete" : "Save"}
      </LoadingButton>
    </DialogFooter>
  )
}
