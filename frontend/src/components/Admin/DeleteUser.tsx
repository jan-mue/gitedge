import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Trash2 } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { usersDeleteUserMutation } from "@/client/@tanstack/react-query.gen"
import {
  Button,
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DropdownMenuItem,
  LoadingButton,
} from "@/components/design-system"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface DeleteUserProps {
  id: string
  onSuccess: () => void
}

const DeleteUser = ({ id, onSuccess }: DeleteUserProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { handleSubmit } = useForm()

  const mutation = useMutation({
    ...usersDeleteUserMutation(),
    onSuccess: () => {
      showSuccessToast("The user was deleted successfully")
      setIsOpen(false)
      onSuccess()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries()
    },
  })

  const onSubmit = async () => {
    mutation.mutate({ path: { user_id: id } })
  }

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuItem variant="destructive" onSelect={(e) => e.preventDefault()} onClick={() => setIsOpen(true)}>
        <Trash2 />
        Delete User
      </DropdownMenuItem>
      <DialogContent appearance="compact">
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Delete User</DialogTitle>
            <DialogDescription>
              All items associated with this user will also be <strong>permanently deleted.</strong> Are you sure? You
              will not be able to undo this action.
            </DialogDescription>
          </DialogHeader>

          <DialogFooter appearance="spaced">
            <DialogClose asChild>
              <Button variant="repository" disabled={mutation.isPending}>
                Cancel
              </Button>
            </DialogClose>
            <LoadingButton variant="destructive" type="submit" loading={mutation.isPending}>
              Delete
            </LoadingButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default DeleteUser
