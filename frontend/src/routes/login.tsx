import { zodResolver } from "@hookform/resolvers/zod"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { useForm } from "react-hook-form"
import { z } from "zod"
import type { Body_login_login_access_token as AccessToken } from "@/client"
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
  Inline,
  Input,
  LoadingButton,
  PasswordInput,
  Link as RouterLink,
} from "@/design-system"
import useAuth, { isLoggedIn } from "@/hooks/useAuth"
import { signupsEnabled } from "@/utils"

const formSchema = z.object({
  username: z.email({ message: "Invalid email address" }),
  password: z
    .string()
    .min(1, { message: "Password is required" })
    .min(8, { message: "Password must be at least 8 characters" }),
}) satisfies z.ZodType<AccessToken>

type FormData = z.infer<typeof formSchema>

export const Route = createFileRoute("/login")({
  component: Login,
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
        title: "Log In - GitEdge",
      },
    ],
  }),
})

function Login() {
  const { loginMutation } = useAuth()
  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      username: "",
      password: "",
    },
  })

  const onSubmit = (data: FormData) => {
    if (loginMutation.isPending) return
    loginMutation.mutate({ body: data })
  }

  return (
    <AuthLayout>
      <Form {...form}>
        <AuthForm onSubmit={form.handleSubmit(onSubmit)}>
          <AuthHeading>
            <AuthTitle>Login to your account</AuthTitle>
          </AuthHeading>

          <FieldStack>
            <FormField
              control={form.control}
              name="username"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Email</FormLabel>
                  <FormControl>
                    <Input data-testid="email-input" placeholder="user@example.com" type="email" {...field} />
                  </FormControl>
                  <FormMessage appearance="compact" />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="password"
              render={({ field }) => (
                <FormItem>
                  <Inline>
                    <FormLabel>Password</FormLabel>
                    <RouterLink to="/recover-password" appearance="recovery">
                      Forgot your password?
                    </RouterLink>
                  </Inline>
                  <FormControl>
                    <PasswordInput data-testid="password-input" placeholder="Password" {...field} />
                  </FormControl>
                  <FormMessage appearance="compact" />
                </FormItem>
              )}
            />

            <LoadingButton type="submit" loading={loginMutation.isPending}>
              Log In
            </LoadingButton>
          </FieldStack>

          <AuthFooter>
            {signupsEnabled ? (
              <>
                Don't have an account yet?{" "}
                <RouterLink to="/signup" appearance="underline">
                  Sign up
                </RouterLink>
              </>
            ) : (
              "Sign-ups are disabled."
            )}
          </AuthFooter>
        </AuthForm>
      </Form>
    </AuthLayout>
  )
}
