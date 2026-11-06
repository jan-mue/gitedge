import { useQuery } from "@tanstack/react-query"
import { repositoriesGetRepositoryOptions } from "@/client/@tanstack/react-query.gen"
import { isLoggedIn } from "@/hooks/useAuth"

export const useRepositoryViewer = (owner: string, repo: string) => {
  const authenticated = isLoggedIn()
  const { data: repository } = useQuery({
    ...repositoriesGetRepositoryOptions({ path: { owner, repo } }),
    enabled: !authenticated,
  })
  return { authenticated, repository }
}
