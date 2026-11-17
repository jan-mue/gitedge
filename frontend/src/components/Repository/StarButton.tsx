import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Star } from "lucide-react"
import { useState } from "react"
import type { StarState } from "@/client"
import {
  repositoriesListRepositoriesQueryKey,
  starsGetStarStateOptions,
  starsGetStarStateQueryKey,
  starsListStargazersQueryKey,
  starsStarRepositoryMutation,
  starsUnstarRepositoryMutation,
} from "@/client/@tanstack/react-query.gen"
import { Button, Link as RouterLink } from "@/components/design-system"
import { StarListMenu } from "./StarListMenu"

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

  const handleSuccess = (next: StarState) => {
    queryClient.setQueryData(starsGetStarStateQueryKey({ path: { owner, repo } }), next)
    queryClient.invalidateQueries({ queryKey: starsListStargazersQueryKey({ path: { owner, repo } }) })
    queryClient.invalidateQueries({ queryKey: repositoriesListRepositoriesQueryKey() })
  }

  const mutation = useMutation({
    ...(state?.is_starred ? starsUnstarRepositoryMutation() : starsStarRepositoryMutation()),
    onSuccess: handleSuccess,
  })

  const star = useMutation({
    ...starsStarRepositoryMutation(),
    onSuccess: handleSuccess,
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
        disabled={mutation.isPending || star.isPending || !state}
        variant="repository"
        size="compact"
        shape="start"
      >
        <Star
          className={`h-3.5 w-3.5 transition-all duration-300 ${
            isStarred ? "fill-starred text-starred" : ""
          } ${animating ? "scale-150" : "scale-100"}`}
          style={animating ? { filter: "drop-shadow(0 0 6px var(--starred))" } : undefined}
        />
        <span>{isStarred ? "Starred" : "Star"}</span>
      </Button>
      <RouterLink
        to="/$owner/$repo/stars"
        params={{ owner, repo }}
        aria-label="View stargazers"
        data-testid="star-count"
        appearance="splitCount"
      >
        {count}
      </RouterLink>
      <StarListMenu
        repository={`${owner}/${repo}`}
        disabled={mutation.isPending || star.isPending || !state}
        ensureStarred={() => (isStarred ? Promise.resolve() : star.mutateAsync({ path: { owner, repo } }))}
      />
    </div>
  )
}

export default StarButton
