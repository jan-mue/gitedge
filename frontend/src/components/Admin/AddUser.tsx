import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"
import { usersCreateUserMutation, usersReadUsersQueryKey } from "@/client/@tanstack/react-query.gen"
import { UserFormFields } from "@/components/Admin/UserFormFields"
import { DialogActionFooter } from "@/components/Common/DialogActionFooter"
import {
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  Form,
} from "@/components/design-system"
import useCustomToast from "@/hooks/useCustomToast"
import { passwordSchema } from "@/lib/password-schema"
import { handleError } from "@/utils"

const formSchema = z
  .object({
    email: z.email({ message: "Invalid email address" }),
    display_name: z.string().optional(),
    password: passwordSchema,
    confirm_password: z.string().min(1, { message: "Please confirm your password" }),
    is_superuser: z.boolean(),
    is_active: z.boolean(),
  })
  .refine((data) => data.password === data.confirm_password, {
    message: "The passwords don't match",
    path: ["confirm_password"],
  })

type FormData = z.infer<typeof formSchema>

const AddUser = () => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      email: "",
      display_name: "",
      password: "",
      confirm_password: "",
      is_superuser: false,
      is_active: false,
    },
  })

  const mutation = useMutation({
    ...usersCreateUserMutation(),
    onSuccess: () => {
      showSuccessToast("User created successfully")
      form.reset()
      setIsOpen(false)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: usersReadUsersQueryKey() })
    },
  })

  const onSubmit = (data: FormData) => {
    mutation.mutate({ body: data })
  }

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <div className="my-4">
          <Button>
            <Plus className="mr-2" />
            Add User
          </Button>
        </div>
      </DialogTrigger>
      <DialogContent appearance="compact">
        <DialogHeader>
          <DialogTitle>Add User</DialogTitle>
          <DialogDescription>Fill in the form below to add a new user to the system.</DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)}>
            <UserFormFields passwordRequired />
            <DialogActionFooter pending={mutation.isPending} />
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default AddUser
