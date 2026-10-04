import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link as RouterLink } from "@tanstack/react-router"
import { Star } from "lucide-react"

import { StarsService } from "@/client"

interface StarButtonProps {
  owner: string
  repo: string
}

const StarButton = ({ owner, repo }: StarButtonProps) => {
  const repoPath = `${owner}/${repo}.git`
  const queryClient = useQueryClient()

  const { data: state } = useQuery({
    queryKey: ["star", repoPath],
    queryFn: async () => (await StarsService.getStarState({ path: { path: repoPath } })).data,
  })

  const mutation = useMutation({
    mutationFn: async () =>
      state?.is_starred
        ? (await StarsService.unstarRepository({ path: { path: repoPath } })).data
        : (await StarsService.starRepository({ path: { path: repoPath } })).data,
    onSuccess: (next) => queryClient.setQueryData(["star", repoPath], next),
  })

  const isStarred = state?.is_starred ?? false
  const count = state?.stars_count ?? 0

  return (
    <div className="flex items-stretch" data-testid="star-button">
      <button
        type="button"
        onClick={() => mutation.mutate()}
        disabled={mutation.isPending}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-l border border-border text-sm transition-colors ${
          isStarred
            ? "bg-warning text-warning-foreground border-warning"
            : "bg-secondary text-foreground hover:bg-accent"
        }`}
      >
        <Star className={`w-3.5 h-3.5 ${isStarred ? "fill-current" : ""}`} />
        <span>{isStarred ? "Starred" : "Star"}</span>
      </button>
      <RouterLink
        to="/$owner/$repo/stars"
        params={{ owner, repo }}
        className="flex items-center px-2.5 py-1.5 rounded-r border border-l-0 border-border bg-secondary text-sm text-foreground hover:bg-accent transition-colors"
        data-testid="star-count"
      >
        {count}
      </RouterLink>
    </div>
  )
}

export default StarButton
