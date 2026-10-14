import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { useForm } from "react-hook-form"
import { z } from "zod"
import { loginRecoverPasswordMutation } from "@/client/@tanstack/react-query.gen"
import { AuthLayout } from "@/components/Common/AuthLayout"
import {
  AuthFooter,
  AuthForm,
  AuthHeading,
  AuthTitle,
  FieldStack,
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
  Input,
  LoadingButton,
  Link as RouterLink,
} from "@/components/design-system"
import { isLoggedIn } from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const formSchema = z.object({
  email: z.email({ message: "Invalid email address" }),
})

type FormData = z.infer<typeof formSchema>

export const Route = createFileRoute("/recover-password")({
  component: RecoverPassword,
  beforeLoad: async () => {
    if (isLoggedIn()) {
      throw redirect({
        to: "/",
      })
    }
  },
  head: () => ({
    meta: [
      {
        title: "Recover Password - GitEdge",
      },
    ],
  }),
})

function RecoverPassword() {
  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      email: "",
    },
  })
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const mutation = useMutation({
    ...loginRecoverPasswordMutation(),
    onSuccess: () => {
      showSuccessToast("Password recovery email sent successfully")
      form.reset()
    },
    onError: handleError.bind(showErrorToast),
  })

  const onSubmit = async (data: FormData) => {
    if (mutation.isPending) return
    mutation.mutate({ path: { email: data.email } })
  }

  return (
    <AuthLayout>
      <Form {...form}>
        <AuthForm onSubmit={form.handleSubmit(onSubmit)}>
          <AuthHeading>
            <AuthTitle>Password Recovery</AuthTitle>
          </AuthHeading>

          <FieldStack>
            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Email</FormLabel>
                  <FormControl>
                    <Input data-testid="email-input" placeholder="user@example.com" type="email" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <LoadingButton type="submit" fullWidth loading={mutation.isPending}>
              Continue
            </LoadingButton>
          </FieldStack>

          <AuthFooter>
            Remember your password?{" "}
            <RouterLink to="/login" appearance="underline">
              Log in
            </RouterLink>
          </AuthFooter>
        </AuthForm>
      </Form>
    </AuthLayout>
  )
}
