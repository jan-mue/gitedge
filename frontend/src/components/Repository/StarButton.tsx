import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
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
import { Button, Link as RouterLink } from "@/design-system"

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
      <Button
        type="button"
        onClick={handleClick}
        aria-pressed={isStarred}
        disabled={mutation.isPending}
        variant="outline"
        size="sm"
        shape="start"
      >
        <Star
          className={`h-3.5 w-3.5 transition-all duration-300 ${
            isStarred ? "fill-warning text-warning" : ""
          } ${animating ? "scale-150" : "scale-100"}`}
          style={animating ? { filter: "drop-shadow(0 0 6px var(--warning))" } : undefined}
        />
        <span>{isStarred ? "Starred" : "Star"}</span>
      </Button>
      <RouterLink to="/$owner/$repo/stars" params={{ owner, repo }} data-testid="star-count" appearance="count">
        {count}
      </RouterLink>
    </div>
  )
}

export default StarButton
