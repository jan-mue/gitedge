import { z } from "zod"

export const passwordSchema = z
  .string()
  .min(1, { message: "Password is required" })
  .min(8, { message: "Password must be at least 8 characters" })

export const passwordConfirmationSchema = z.object({
  new_password: passwordSchema,
  confirm_password: z.string().min(1, { message: "Password confirmation is required" }),
})

export const matchingPasswords = (data: { new_password: string; confirm_password: string }) =>
  data.new_password === data.confirm_password

export const passwordMismatch = { message: "The passwords don't match", path: ["confirm_password"] }
