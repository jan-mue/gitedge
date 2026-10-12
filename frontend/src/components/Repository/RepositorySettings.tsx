import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { Settings, Trash2 } from "lucide-react"
import { useEffect, useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"
import {
  repositoriesDeleteRepositoryMutation,
  repositoriesGetRepositoryOptions,
  repositoriesListBranchesOptions,
  repositoriesUpdateRepositoryMutation,
} from "@/client/@tanstack/react-query.gen"
import {
  Button,
  DangerZone,
  DangerZoneAction,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  ExternalLink,
  Input,
  Label,
  LoadingButton,
  NativeSelect,
  Textarea,
} from "@/components/design-system"
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
  if (isPending) return <RepositoryLoading label="Loading repository settings" />
  if (isError) return <RepositoryError message="Unable to load settings." retry={() => refetch()} />
  if (!user || (user.name.toLowerCase() !== owner.toLowerCase() && !user.is_superuser))
    return <RepositoryError message="Only the repository owner or an administrator can change these settings." />
  const fullName = `${owner}/${repo}`
  return (
    <div className="grid min-w-0 gap-6 md:grid-cols-[16rem_minmax(0,1fr)]">
      <aside className="min-w-0 md:h-fit md:rounded md:border md:bg-card">
        <h2 className="hidden border-b bg-secondary px-4 py-3 text-lg font-semibold md:block">Settings</h2>
        <nav
          className="flex gap-1 overflow-x-auto text-sm md:flex-col md:gap-0 md:overflow-visible"
          aria-label="Repository settings"
        >
          <ExternalLink href="#basic-settings" appearance="settings">
            <Settings className="size-4 shrink-0" aria-hidden="true" />
            Repository
          </ExternalLink>
          <ExternalLink href="#danger-zone" appearance="settingsDanger">
            <Trash2 className="size-4 shrink-0" aria-hidden="true" />
            Danger zone
          </ExternalLink>
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
              <Label htmlFor="repository-name" appearance="field">
                Repository name *
              </Label>
              <Input id="repository-name" {...register("name")} aria-invalid={Boolean(errors.name)} />
              {errors.name && <p className="mt-1 text-sm text-destructive">{errors.name.message}</p>}
            </div>
            <div>
              <Label htmlFor="repository-description" appearance="field">
                Description
              </Label>
              <Textarea id="repository-description" {...register("description")} />
              {errors.description && <p className="text-sm text-destructive">{errors.description.message}</p>}
            </div>
            <div>
              <Label htmlFor="default-branch" appearance="field">
                Default branch
              </Label>
              {branches?.length ? (
                <NativeSelect id="default-branch" {...register("default_branch")}>
                  {branches.map((branch) => (
                    <option key={branch.name} value={branch.name}>
                      {branch.name}
                    </option>
                  ))}
                </NativeSelect>
              ) : (
                <Input id="default-branch" {...register("default_branch")} />
              )}
              {errors.default_branch && <p className="text-sm text-destructive">{errors.default_branch.message}</p>}
              <p className="mt-1 text-xs text-muted-foreground">The branch shown when visitors open the repository.</p>
            </div>
            <p className="text-sm text-muted-foreground">Visibility: {data.is_private ? "Private" : "Public"}</p>
            <LoadingButton type="submit" loading={update.isPending} disabled={!isDirty || remove.isPending}>
              Save settings
            </LoadingButton>
          </form>
        </section>
        <DangerZone id="danger-zone">
          <DangerZoneAction
            title="Delete this repository"
            description={
              <>
                <p>Permanently delete code, issues, pull requests, releases, and repository activity.</p>
                <p className="mt-1 text-xs">Independent forks will be preserved.</p>
              </>
            }
            action={
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
                  <Button variant="dangerOutline" size="danger" disabled={update.isPending}>
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
                  <Label htmlFor="delete-confirmation" appearance="field">
                    Repository full name
                  </Label>
                  <Input
                    id="delete-confirmation"
                    value={confirmation}
                    onChange={(event) => setConfirmation(event.target.value)}
                    autoComplete="off"
                  />
                  <DialogFooter>
                    <Button variant="repository" disabled={remove.isPending} onClick={() => setDeleteOpen(false)}>
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
            }
          />
        </DangerZone>
      </div>
    </div>
  )
}
export default RepositorySettings
