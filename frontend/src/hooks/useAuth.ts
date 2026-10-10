import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"

import {
  loginLoginAccessTokenMutation,
  usersReadUserMeOptions,
  usersReadUsersQueryKey,
  usersRegisterUserMutation,
} from "@/client/@tanstack/react-query.gen"
import { handleError } from "@/utils"
import useCustomToast from "./useCustomToast"

const isLoggedIn = () => {
  return localStorage.getItem("access_token") !== null
}

const useAuth = () => {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()

  const { data: user } = useQuery({
    ...usersReadUserMeOptions(),
    enabled: isLoggedIn(),
  })

  const signUpMutation = useMutation({
    ...usersRegisterUserMutation(),
    onSuccess: () => {
      navigate({ to: "/login" })
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: usersReadUsersQueryKey() })
    },
  })

  const loginMutation = useMutation({
    ...loginLoginAccessTokenMutation(),
    onSuccess: (data) => {
      localStorage.setItem("access_token", data.access_token)
      queryClient.clear()
      navigate({ to: "/" })
    },
    onError: handleError.bind(showErrorToast),
  })

  const logout = () => {
    localStorage.removeItem("access_token")
    queryClient.clear()
    navigate({ to: "/login" })
  }

  return {
    signUpMutation,
    loginMutation,
    logout,
    user,
  }
}

export { isLoggedIn }
export default useAuth
