import { zodResolver } from "@hookform/resolvers/zod"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { useForm } from "react-hook-form"
import { z } from "zod"
import { AuthLayout } from "@/components/Common/AuthLayout"
import { FormInputField } from "@/components/Common/FormInputField"
import {
  AuthFooter,
  AuthForm,
  AuthHeading,
  AuthTitle,
  FieldStack,
  Form,
  LoadingButton,
  Link as RouterLink,
} from "@/components/design-system"
import useAuth, { isLoggedIn } from "@/hooks/useAuth"
import { passwordSchema, signupsEnabled } from "@/utils"

const formSchema = z
  .object({
    email: z.email({ message: "Invalid email address" }),
    display_name: z.string().min(1, { message: "Full Name is required" }),
    password: passwordSchema,
    confirm_password: z.string().min(1, { message: "Password confirmation is required" }),
  })
  .refine((data) => data.password === data.confirm_password, {
    message: "The passwords don't match",
    path: ["confirm_password"],
  })

type FormData = z.infer<typeof formSchema>

export const Route = createFileRoute("/signup")({
  component: SignUp,
  beforeLoad: async () => {
    if (!signupsEnabled) {
      throw redirect({
        to: "/login",
      })
    }
    if (isLoggedIn()) {
      throw redirect({
        to: "/",
      })
    }
  },
  head: () => ({
    meta: [
      {
        title: "Sign Up - GitEdge",
      },
    ],
  }),
})

function SignUp() {
  const { signUpMutation } = useAuth()
  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      email: "",
      display_name: "",
      password: "",
      confirm_password: "",
    },
  })

  const onSubmit = (data: FormData) => {
    if (signUpMutation.isPending) return

    // exclude confirm_password from submission data
    const { confirm_password: _confirm_password, ...submitData } = data
    signUpMutation.mutate({ body: submitData })
  }

  return (
    <AuthLayout>
      <Form {...form}>
        <AuthForm onSubmit={form.handleSubmit(onSubmit)}>
          <AuthHeading>
            <AuthTitle>Create an account</AuthTitle>
          </AuthHeading>

          <FieldStack>
            <FormInputField
              control={form.control}
              name="display_name"
              label="Full Name"
              testId="full-name-input"
              placeholder="User"
              type="text"
            />

            <FormInputField
              control={form.control}
              name="email"
              label="Email"
              testId="email-input"
              placeholder="user@example.com"
              type="email"
            />

            <FormInputField
              control={form.control}
              name="password"
              label="Password"
              testId="password-input"
              placeholder="Password"
              passwordToggle
              type="password"
            />

            <FormInputField
              control={form.control}
              name="confirm_password"
              label="Confirm Password"
              testId="confirm-password-input"
              placeholder="Confirm Password"
              passwordToggle
              type="password"
            />

            <LoadingButton type="submit" fullWidth loading={signUpMutation.isPending}>
              Sign Up
            </LoadingButton>
          </FieldStack>

          <AuthFooter>
            Already have an account?{" "}
            <RouterLink to="/login" appearance="underline">
              Log in
            </RouterLink>
          </AuthFooter>
        </AuthForm>
      </Form>
    </AuthLayout>
  )
}
