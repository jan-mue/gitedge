import { zodResolver } from "@hookform/resolvers/zod"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { useForm } from "react-hook-form"
import { z } from "zod"
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
  PasswordInput,
  Link as RouterLink,
} from "@/design-system"
import useAuth, { isLoggedIn } from "@/hooks/useAuth"
import { signupsEnabled } from "@/utils"

const formSchema = z
  .object({
    email: z.email({ message: "Invalid email address" }),
    display_name: z.string().min(1, { message: "Full Name is required" }),
    password: z
      .string()
      .min(1, { message: "Password is required" })
      .min(8, { message: "Password must be at least 8 characters" }),
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
            <FormField
              control={form.control}
              name="display_name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Full Name</FormLabel>
                  <FormControl>
                    <Input data-testid="full-name-input" placeholder="User" type="text" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

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

            <FormField
              control={form.control}
              name="password"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Password</FormLabel>
                  <FormControl>
                    <PasswordInput data-testid="password-input" placeholder="Password" {...field} />
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
