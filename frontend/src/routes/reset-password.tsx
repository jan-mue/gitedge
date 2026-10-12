import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation } from "@tanstack/react-query"
import { createFileRoute, redirect, useNavigate } from "@tanstack/react-router"
import { useForm } from "react-hook-form"
import { z } from "zod"
import { loginResetPasswordMutation } from "@/client/@tanstack/react-query.gen"
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
  LoadingButton,
  PasswordInput,
  Link as RouterLink,
} from "@/components/design-system"
import { isLoggedIn } from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const searchSchema = z.object({
  token: z.string().catch(""),
})

const formSchema = z
  .object({
    new_password: z
      .string()
      .min(1, { message: "Password is required" })
      .min(8, { message: "Password must be at least 8 characters" }),
    confirm_password: z.string().min(1, { message: "Password confirmation is required" }),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: "The passwords don't match",
    path: ["confirm_password"],
  })

type FormData = z.infer<typeof formSchema>

export const Route = createFileRoute("/reset-password")({
  component: ResetPassword,
  validateSearch: searchSchema,
  beforeLoad: async ({ search }) => {
    if (isLoggedIn()) {
      throw redirect({ to: "/" })
    }
    if (!search.token) {
      throw redirect({ to: "/login" })
    }
  },
  head: () => ({
    meta: [
      {
        title: "Reset Password - GitEdge",
      },
    ],
  }),
})

function ResetPassword() {
  const { token } = Route.useSearch()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const navigate = useNavigate()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      new_password: "",
      confirm_password: "",
    },
  })

  const mutation = useMutation({
    ...loginResetPasswordMutation(),
    onSuccess: () => {
      showSuccessToast("Password updated successfully")
      form.reset()
      navigate({ to: "/login" })
    },
    onError: handleError.bind(showErrorToast),
  })

  const onSubmit = (data: FormData) => {
    mutation.mutate({ body: { new_password: data.new_password, token } })
  }

  return (
    <AuthLayout>
      <Form {...form}>
        <AuthForm onSubmit={form.handleSubmit(onSubmit)}>
          <AuthHeading>
            <AuthTitle>Reset Password</AuthTitle>
          </AuthHeading>

          <FieldStack>
            <FormField
              control={form.control}
              name="new_password"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>New Password</FormLabel>
                  <FormControl>
                    <PasswordInput data-testid="new-password-input" placeholder="New Password" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="confirm_password"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Confirm Password</FormLabel>
                  <FormControl>
                    <PasswordInput data-testid="confirm-password-input" placeholder="Confirm Password" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <LoadingButton type="submit" fullWidth loading={mutation.isPending}>
              Reset Password
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
