import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Check, ChevronDown, GitMerge, GitPullRequestArrow, Layers } from "lucide-react"
import { useState } from "react"
import type { MergeMethod, PullRequestPublic } from "@/client"
import {
  repositoriesGetPullRequestEventsQueryKey,
  repositoriesGetPullRequestQueryKey,
  repositoriesGetRepositoryOptions,
  repositoriesListPullRequestsQueryKey,
  repositoriesMergePullRequestMutation,
} from "@/client/@tanstack/react-query.gen"
import {
  Button,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/design-system"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const methods = [
  {
    value: "merge",
    label: "Create merge commit",
    description: "Keep all commits and join both branches.",
    setting: "allow_merge_commit",
    icon: GitMerge,
  },
  {
    value: "squash",
    label: "Squash and merge",
    description: "Combine the PR into one commit.",
    setting: "allow_squash_merge",
    icon: Layers,
  },
  {
    value: "rebase",
    label: "Rebase and merge",
    description: "Replay commits onto the base branch.",
    setting: "allow_rebase_merge",
    icon: GitPullRequestArrow,
  },
] as const

export const PullRequestMergeButton = ({
  owner,
  repo,
  pull,
}: {
  owner: string
  repo: string
  pull: PullRequestPublic
}) => {
  const { user } = useAuth()
  const client = useQueryClient()
  const { showErrorToast } = useCustomToast()
  const [selected, setSelected] = useState<MergeMethod>("merge")
  const settings = useQuery({
    ...repositoriesGetRepositoryOptions({ path: { owner, repo } }),
    enabled: Boolean(user && (user.name.toLowerCase() === owner.toLowerCase() || user.is_superuser)),
    staleTime: 30_000,
  })
  const mutation = useMutation({
    ...repositoriesMergePullRequestMutation(),
    onError: handleError.bind(showErrorToast),
    onSuccess: async (updated) => {
      client.setQueryData(repositoriesGetPullRequestQueryKey({ path: { owner, repo, number: pull.number } }), updated)
      await Promise.all([
        client.invalidateQueries({
          queryKey: repositoriesGetPullRequestEventsQueryKey({ path: { owner, repo, number: pull.number } }),
        }),
        client.invalidateQueries({ queryKey: repositoriesListPullRequestsQueryKey({ path: { owner, repo } }) }),
        // Branches, source and file/commit views must reflect the published Git refs.
        client.invalidateQueries({
          predicate: (query) =>
            query.queryKey.some(
              (key) =>
                typeof key === "object" &&
                key !== null &&
                "path" in key &&
                (key.path as { owner?: string; repo?: string } | undefined)?.owner === owner &&
                (key.path as { repo?: string } | undefined)?.repo === repo,
            ),
        }),
      ])
    },
  })
  if (!user || (user.name.toLowerCase() !== owner.toLowerCase() && !user.is_superuser))
    return <p className="text-sm text-muted-foreground">Only the repository owner can merge this pull request.</p>
  if (settings.isError)
    return (
      <Button variant="repository" size="compact" onClick={() => settings.refetch()}>
        Retry loading merge options
      </Button>
    )
  const enabled = methods.filter((method) => settings.data?.[method.setting] !== false)
  const method = enabled.find((item) => item.value === selected) ?? enabled[0]
  if (!method)
    return <p className="text-sm text-muted-foreground">All merge methods are disabled in repository settings.</p>
  const Icon = method.icon
  return (
    <fieldset className="inline-flex" aria-label="Merge pull request">
      <Button
        variant="success"
        size="compact"
        shape="start"
        loading={mutation.isPending}
        disabled={!settings.data}
        data-testid="merge-pr"
        onClick={() => mutation.mutate({ path: { owner, repo, number: pull.number }, body: { method: method.value } })}
      >
        <Icon className="size-4" />
        {method.label}
      </Button>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="success"
            size="icon-sm"
            shape="end"
            aria-label="Choose merge method"
            disabled={!settings.data || mutation.isPending}
          >
            <ChevronDown className="size-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          {enabled.map((item) => (
            <DropdownMenuItem key={item.value} onSelect={() => setSelected(item.value)}>
              <div className="flex items-start gap-2 py-1">
                <span className="mt-0.5 flex size-4 shrink-0 items-center">
                  {method.value === item.value && <Check className="size-4" />}
                </span>
                <span>
                  <span className="block font-medium">{item.label}</span>
                  <span className="block text-xs text-muted-foreground">{item.description}</span>
                </span>
              </div>
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    </fieldset>
  )
}
