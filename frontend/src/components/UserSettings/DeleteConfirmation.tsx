import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useForm } from "react-hook-form"
import { usersDeleteUserMeMutation, usersReadUserMeQueryKey } from "@/client/@tanstack/react-query.gen"
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
  LoadingButton,
} from "@/components/design-system"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const DeleteConfirmation = () => {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { handleSubmit } = useForm()
  const { logout } = useAuth()

  const mutation = useMutation({
    ...usersDeleteUserMeMutation(),
    onSuccess: () => {
      showSuccessToast("Your account has been successfully deleted")
      logout()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: usersReadUserMeQueryKey() })
    },
  })

  const onSubmit = async () => {
    mutation.mutate({})
  }

  return (
    <Dialog>
      <DialogTrigger asChild>
        <div className="mt-3">
          <Button variant="destructive">Delete Account</Button>
        </div>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Confirmation Required</DialogTitle>
            <DialogDescription>
              All your account data will be <strong>permanently deleted.</strong> If you are sure, please click{" "}
              <strong>"Confirm"</strong> to proceed. This action cannot be undone.
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

export default DeleteConfirmation
