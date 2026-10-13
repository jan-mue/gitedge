import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { Settings, Trash2 } from "lucide-react"
import { useEffect, useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"
import {
  authorizationGetPermissionsOptions,
  repositoriesDeleteRepositoryMutation,
  repositoriesGetRepositoryOptions,
  repositoriesListBranchesOptions,
  repositoriesUpdateRepositoryMutation,
} from "@/client/@tanstack/react-query.gen"
import RepositoryCollaborators from "@/components/Repository/RepositoryCollaborators"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import RepositoryLoading, { RepositoryError } from "./RepositoryLoading"

const schema = z.object({
  name: z
    .string()
    .min(1, "Repository name is required")
    .max(255)
    .regex(/^[A-Za-z0-9_.-]+$/, "Use letters, numbers, dots, underscores, or hyphens"),
  description: z.string().max(10000),
  default_branch: z.string().min(1, "Default branch is required"),
  is_private: z.boolean(),
})
type SettingsForm = z.infer<typeof schema>

const RepositorySettings = ({ owner, repo }: { owner: string; repo: string }) => {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [confirmation, setConfirmation] = useState("")
  const { data, isPending, isError, refetch } = useQuery(repositoriesGetRepositoryOptions({ path: { owner, repo } }))
  const permissions = useQuery(authorizationGetPermissionsOptions({ path: { owner, repo } }))
  const { data: branches } = useQuery(repositoriesListBranchesOptions({ path: { owner, repo } }))
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isDirty },
  } = useForm<SettingsForm>({ resolver: zodResolver(schema) })
  useEffect(() => {
    if (data)
      reset({
        name: data.name,
        description: data.description ?? "",
        default_branch: data.default_branch,
        is_private: data.is_private,
      })
  }, [data, reset])
  const update = useMutation({
    ...repositoriesUpdateRepositoryMutation(),
    onSuccess: async (updated) => {
      await queryClient.invalidateQueries()
      reset({
        name: updated.name,
        description: updated.description ?? "",
        default_branch: updated.default_branch,
        is_private: updated.is_private,
      })
      showSuccessToast("Repository settings saved")
      if (updated.name !== repo)
        navigate({ to: "/$owner/$repo/settings", params: { owner, repo: updated.name }, replace: true })
    },
    onError: handleError.bind(showErrorToast),
  })
  const remove = useMutation({
    ...repositoriesDeleteRepositoryMutation(),
    onSuccess: () => {
      queryClient.clear()
      showSuccessToast("Repository deleted")
      navigate({ to: "/profile/$username", params: { username: owner } })
    },
    onError: handleError.bind(showErrorToast),
  })
  if (isPending || permissions.isPending) return <RepositoryLoading label="Loading repository settings" />
  if (isError) return <RepositoryError message="Unable to load settings." retry={() => refetch()} />
  if (!user || !permissions.data?.admin)
    return <RepositoryError message="Repository admin permission is required to change these settings." />
  const fullName = `${owner}/${repo}`
  return (
    <div className="grid min-w-0 gap-6 md:grid-cols-[16rem_minmax(0,1fr)]">
      <aside className="min-w-0 md:h-fit md:rounded md:border md:bg-card">
        <h2 className="hidden border-b bg-secondary px-4 py-3 text-lg font-semibold md:block">Settings</h2>
        <nav
          className="flex gap-1 overflow-x-auto text-sm md:flex-col md:gap-0 md:overflow-visible"
          aria-label="Repository settings"
        >
          <a
            href="#basic-settings"
            className="flex shrink-0 items-center gap-2 whitespace-nowrap rounded bg-accent/50 px-3 py-2 transition-colors hover:bg-accent focus-visible:outline-2 focus-visible:outline-ring md:rounded-none md:border-b md:bg-transparent md:px-4 md:py-3"
          >
            <Settings className="size-4 shrink-0" aria-hidden="true" />
            Repository
          </a>
          <a href="#collaborators" className="px-4 py-3 text-sm hover:bg-accent">
            Collaborators
          </a>
          {permissions.data.owner && (
            <a
              href="#danger-zone"
              className="flex shrink-0 items-center gap-2 whitespace-nowrap rounded bg-accent/50 px-3 py-2 text-destructive transition-colors hover:bg-accent focus-visible:outline-2 focus-visible:outline-ring md:rounded-none md:bg-transparent md:px-4 md:py-3"
            >
              <Trash2 className="size-4 shrink-0" aria-hidden="true" />
              Danger zone
            </a>
          )}
        </nav>
      </aside>
      <div className="min-w-0 space-y-6">
        <section id="basic-settings" className="overflow-hidden rounded border bg-card">
          <h3 className="border-b bg-secondary px-4 py-3 text-xl font-semibold">Basic settings</h3>
          <form
            onSubmit={handleSubmit((body) => update.mutate({ path: { owner, repo }, body }))}
            className="space-y-4 p-4"
          >
            <div>
              <label htmlFor="repository-name" className="mb-1 block text-sm font-medium">
                Repository name *
              </label>
              <Input id="repository-name" {...register("name")} aria-invalid={Boolean(errors.name)} />
              {errors.name && <p className="mt-1 text-sm text-destructive">{errors.name.message}</p>}
            </div>
            <div>
              <label htmlFor="repository-description" className="mb-1 block text-sm font-medium">
                Description
              </label>
              <textarea
                id="repository-description"
                {...register("description")}
                className="min-h-24 w-full rounded border bg-background px-3 py-2 text-sm"
              />
              {errors.description && <p className="text-sm text-destructive">{errors.description.message}</p>}
            </div>
            <div>
              <label htmlFor="default-branch" className="mb-1 block text-sm font-medium">
                Default branch
              </label>
              {branches?.length ? (
                <select
                  id="default-branch"
                  {...register("default_branch")}
                  className="w-full rounded border bg-background px-3 py-2 text-sm"
                >
                  {branches.map((branch) => (
                    <option key={branch.name} value={branch.name}>
                      {branch.name}
                    </option>
                  ))}
                </select>
              ) : (
                <Input id="default-branch" {...register("default_branch")} />
              )}
              {errors.default_branch && <p className="text-sm text-destructive">{errors.default_branch.message}</p>}
              <p className="mt-1 text-xs text-muted-foreground">The branch shown when visitors open the repository.</p>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" {...register("is_private")} />
              Private repository
            </label>
            <p className="text-xs text-muted-foreground">
              Public repositories allow anyone to read and clone. Private repositories require authentication and a
              repository role.
            </p>
            <LoadingButton type="submit" loading={update.isPending} disabled={!isDirty || remove.isPending}>
              Save settings
            </LoadingButton>
          </form>
        </section>
        <RepositoryCollaborators owner={owner} repo={repo} canManageOwners={permissions.data.owner} />
        {permissions.data.owner && (
          <section id="danger-zone" className="overflow-hidden rounded border border-destructive bg-card">
            <h3 className="border-b border-destructive bg-destructive/10 px-4 py-3 text-xl font-semibold text-destructive">
              Danger zone
            </h3>
            <div className="flex flex-wrap items-center justify-between gap-4 p-4">
              <div>
                <p className="font-medium">Delete this repository</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Permanently delete code, issues, pull requests, releases, and repository activity.
                </p>
                <p className="mt-1 text-xs text-muted-foreground">Independent forks will be preserved.</p>
              </div>
              <Dialog
                open={deleteOpen}
                onOpenChange={(open) => {
                  if (!remove.isPending) {
                    setDeleteOpen(open)
                    setConfirmation("")
                  }
                }}
              >
                <DialogTrigger asChild>
                  <Button variant="destructive" disabled={update.isPending}>
                    Delete this repository
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Delete {fullName}?</DialogTitle>
                    <DialogDescription>
                      This is permanent. All code and repository records will be deleted. Type {fullName} to confirm.
                    </DialogDescription>
                  </DialogHeader>
                  <label htmlFor="delete-confirmation" className="text-sm font-medium">
                    Repository full name
                  </label>
                  <Input
                    id="delete-confirmation"
                    value={confirmation}
                    onChange={(event) => setConfirmation(event.target.value)}
                    autoComplete="off"
                  />
                  <DialogFooter>
                    <Button variant="outline" disabled={remove.isPending} onClick={() => setDeleteOpen(false)}>
                      Cancel
                    </Button>
                    <LoadingButton
                      variant="destructive"
                      loading={remove.isPending}
                      disabled={confirmation !== fullName}
                      onClick={() => remove.mutate({ path: { owner, repo } })}
                    >
                      Delete repository
                    </LoadingButton>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </div>
          </section>
        )}
      </div>
    </div>
  )
}
export default RepositorySettings
