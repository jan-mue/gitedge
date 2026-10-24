export function storybookSession() {
  const previous = localStorage.getItem("access_token")
  localStorage.setItem("access_token", "storybook-session")
  return () => {
    if (previous === null) localStorage.removeItem("access_token")
    else localStorage.setItem("access_token", previous)
  }
}

export const storybookUser = {
  id: "00000000-0000-0000-0000-000000000001",
  name: "jan-mue",
  email: "jan@example.com",
  is_active: true,
}
