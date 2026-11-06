import { redirect } from "@tanstack/react-router"
import { isLoggedIn } from "@/hooks/useAuth"

export const requireSession = () => {
  if (!isLoggedIn()) throw redirect({ to: "/login" })
}
