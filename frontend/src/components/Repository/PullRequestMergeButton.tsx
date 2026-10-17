import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  Check,
  ChevronDown,
  CircleCheck,
  GitMerge,
  GitPullRequestArrow,
  Layers,
  LoaderCircle,
  TriangleAlert,
} from "lucide-react"
import { useState } from "react"
import type { MergeMethod, PullRequestPublic } from "@/client"
import {
  repositoriesGetPullRequestEventsQueryKey,
  repositoriesGetPullRequestMergeabilityOptions,
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
import { extractErrorMessage } from "@/utils"

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
  const [selected, setSelected] = useState<MergeMethod>("merge")
  const canMerge = Boolean(user && (user.name.toLowerCase() === owner.toLowerCase() || user.is_superuser))
  const settings = useQuery({
    ...repositoriesGetRepositoryOptions({ path: { owner, repo } }),
    enabled: pull.state === "open",
    staleTime: 30_000,
  })
  const enabled = methods.filter((method) => settings.data?.[method.setting] !== false)
  const method = enabled.find((item) => item.value === selected) ?? enabled[0]
  const mergeability = useQuery({
    ...repositoriesGetPullRequestMergeabilityOptions({
      path: { owner, repo, number: pull.number },
      query: { method: method?.value ?? "merge" },
    }),
    enabled: Boolean(settings.data && method) && pull.state === "open",
    refetchInterval: 30_000,
    refetchOnWindowFocus: "always",
    retry: 1,
  })
  const mutation = useMutation({
    ...repositoriesMergePullRequestMutation(),
    onError: () => mergeability.refetch(),
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
  if (settings.isError)
    return (
      <Button variant="repository" size="compact" onClick={() => settings.refetch()}>
        Retry loading merge options
      </Button>
    )
  if (!method)
    return <p className="text-sm text-muted-foreground">All merge methods are disabled in repository settings.</p>
  const Icon = method.icon
  const checking = !settings.data || mergeability.isPending || mergeability.isFetching
  const ready = !checking && !mergeability.isError && mergeability.data?.mergeable === true
  const conflicts = mergeability.data?.conflicting_files ?? []
  return (
    <div className="space-y-3">
      <div role="status" aria-live="polite" className="flex items-start gap-3" data-testid="mergeability-status">
        {checking ? (
          <LoaderCircle className="mt-0.5 size-5 shrink-0 animate-spin text-muted-foreground motion-reduce:animate-none" />
        ) : ready ? (
          <CircleCheck className="mt-0.5 size-5 shrink-0 text-success" />
        ) : (
          <TriangleAlert className="mt-0.5 size-5 shrink-0 text-muted-foreground" />
        )}
        <div className="min-w-0 space-y-1 text-sm">
          <p className="font-medium">
            {checking
              ? "Checking whether this pull request can be merged…"
              : mergeability.isError
                ? "Unable to check for merge conflicts"
                : ready
                  ? "This branch has no conflicts with the base branch"
                  : conflicts.length
                    ? "This branch has conflicts that must be resolved"
                    : "This pull request cannot be merged"}
          </p>
          {!checking && !ready && (
            <>
              <p className="text-muted-foreground">
                {mergeability.isError
                  ? "Try checking again before merging."
                  : conflicts.length
                    ? "Resolve the conflicts on the PR branch before merging."
                    : mergeability.data?.reason}
              </p>
              {conflicts.length > 0 && (
                <ul className="max-h-40 overflow-auto font-mono text-xs" aria-label="Conflicting files">
                  {conflicts.map((path) => (
                    <li key={path} className="break-all py-0.5">
                      {path}
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>
      </div>
      {mutation.isError && (
        <p role="alert" className="max-w-prose break-words text-sm text-foreground">
          {extractErrorMessage(mutation.error)}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-3">
        {canMerge ? (
          <fieldset className="inline-flex" aria-label="Merge pull request">
            <Button
              variant="success"
              size="compact"
              shape="start"
              loading={mutation.isPending}
              disabled={!ready || mutation.isPending}
              data-testid="merge-pr"
              onClick={() =>
                mutation.mutate({
                  path: { owner, repo, number: pull.number },
                  body: {
                    method: method.value,
                    head_commit: mergeability.data?.head_commit,
                    base_commit: mergeability.data?.base_commit,
                  },
                })
              }
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
                  <DropdownMenuItem
                    key={item.value}
                    onSelect={() => {
                      setSelected(item.value)
                      mutation.reset()
                    }}
                  >
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
        ) : (
          <p className="text-sm text-muted-foreground">Only the repository owner can merge this pull request.</p>
        )}
        <Button
          variant="ghost"
          size="compact"
          disabled={checking || mutation.isPending}
          onClick={() => {
            mutation.reset()
            void mergeability.refetch()
          }}
        >
          Check again
        </Button>
      </div>
    </div>
  )
}
