import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link as RouterLink } from "@tanstack/react-router"
import { Star } from "lucide-react"
import { useState } from "react"

import {
  repositoriesListRepositoriesQueryKey,
  starsGetStarStateOptions,
  starsGetStarStateQueryKey,
  starsListStargazersQueryKey,
  starsStarRepositoryMutation,
  starsUnstarRepositoryMutation,
} from "@/client/@tanstack/react-query.gen"

interface StarButtonProps {
  owner: string
  repo: string
}

const StarButton = ({ owner, repo }: StarButtonProps) => {
  const queryClient = useQueryClient()
  const [animating, setAnimating] = useState(false)

  const { data: state } = useQuery({
    ...starsGetStarStateOptions({ path: { owner, repo } }),
  })

  const mutation = useMutation({
    ...(state?.is_starred ? starsUnstarRepositoryMutation() : starsStarRepositoryMutation()),
    onSuccess: (next) => {
      queryClient.setQueryData(starsGetStarStateQueryKey({ path: { owner, repo } }), next)
      queryClient.invalidateQueries({ queryKey: starsListStargazersQueryKey({ path: { owner, repo } }) })
      queryClient.invalidateQueries({ queryKey: repositoriesListRepositoriesQueryKey() })
    },
  })

  const isStarred = state?.is_starred ?? false
  const count = state?.stars_count ?? 0

  const handleClick = () => {
    if (!isStarred) {
      setAnimating(true)
      setTimeout(() => setAnimating(false), 600)
    }
    mutation.mutate({ path: { owner, repo } })
  }

  return (
    <div className="flex items-stretch" data-testid="star-button">
      <button
        type="button"
        onClick={handleClick}
        disabled={mutation.isPending}
        className="flex items-center gap-1.5 rounded-l border border-r-0 border-border bg-secondary px-3 py-1.5 text-sm text-foreground transition-colors hover:bg-accent disabled:opacity-50"
      >
        <Star
          className={`h-3.5 w-3.5 transition-all duration-300 ${
            isStarred ? "fill-[hsl(45,100%,50%)] text-[hsl(45,100%,50%)]" : ""
          } ${animating ? "scale-150" : "scale-100"}`}
          style={animating ? { filter: "drop-shadow(0 0 6px hsl(45, 100%, 50%))" } : undefined}
        />
        <span>{isStarred ? "Starred" : "Star"}</span>
      </button>
      <RouterLink
        to="/$owner/$repo/stars"
        params={{ owner, repo }}
        data-testid="star-count"
        className="flex items-center justify-center rounded-r border border-border bg-secondary px-2.5 py-1.5 text-sm font-medium text-foreground transition-colors hover:bg-accent"
      >
        {count}
      </RouterLink>
    </div>
  )
}

export default StarButton
