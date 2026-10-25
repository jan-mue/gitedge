import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { GitMerge, Settings, Trash2 } from "lucide-react"
import { useEffect, useState } from "react"
import { Controller, useForm } from "react-hook-form"
import { z } from "zod"
import type { Repository } from "@/client"
import {
  repositoriesDeleteRepositoryMutation,
  repositoriesGetRepositoryOptions,
  repositoriesListBranchesOptions,
  repositoriesUpdateRepositoryMutation,
} from "@/client/@tanstack/react-query.gen"
import {
  Button,
  Checkbox,
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
  SelectField,
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
  allow_merge_commit: z.boolean(),
  allow_squash_merge: z.boolean(),
  allow_rebase_merge: z.boolean(),
  merge_commit_message: z.enum(["default", "title", "title_description", "title_commits"]),
  squash_commit_message: z.enum(["default", "title", "title_description", "title_commits"]),
  rebase_commit_message: z.enum(["default", "title", "title_description", "title_commits"]),
  delete_branch_on_merge: z.boolean(),
  default_branch: z.string().min(1, "Default branch is required"),
})
type SettingsForm = z.infer<typeof schema>

const mergeDefaults = {
  allow_merge_commit: true,
  allow_squash_merge: true,
  allow_rebase_merge: true,
  merge_commit_message: "default",
  squash_commit_message: "title_description",
  rebase_commit_message: "default",
  delete_branch_on_merge: true,
} satisfies Partial<SettingsForm>
type MergeSettings = Pick<SettingsForm, keyof typeof mergeDefaults>
const mergeFormValues = (data: Partial<Repository>): MergeSettings =>
  Object.fromEntries(
    Object.entries(mergeDefaults).map(([key, fallback]) => [key, data[key as keyof MergeSettings] ?? fallback]),
  ) as MergeSettings

const mergeMethods = [
  {
    enabled: "allow_merge_commit",
    message: "merge_commit_message",
    label: "Create merge commit",
    description: "Keep the original commits and create a commit with two parents.",
  },
  {
    enabled: "allow_squash_merge",
    message: "squash_commit_message",
    label: "Squash and merge",
    description: "Combine all PR changes into one commit.",
  },
  {
    enabled: "allow_rebase_merge",
    message: "rebase_commit_message",
    label: "Rebase and merge",
    description:
      "Replay each commit onto the base. The message template applies to the final commit; earlier messages and authors are preserved.",
  },
] as const
const messageOptions = [
  { value: "default", label: "Default: Merge … into …" },
  { value: "title", label: "PR title" },
  { value: "title_description", label: "PR title and description" },
  { value: "title_commits", label: "PR title and commit details" },
]
const useRepositorySettings = ({ owner, repo }: { owner: string; repo: string }) => {
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
    control,
    handleSubmit,
    reset,
    formState: { errors, isDirty },
  } = useForm<SettingsForm>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", description: "", default_branch: "main", ...mergeFormValues({}) },
  })
  useEffect(() => {
    if (data)
      reset({
        ...mergeFormValues(data),
        name: data.name,
        description: data.description ?? "",
        default_branch: data.default_branch ?? "main",
      })
  }, [data, reset])
  const update = useMutation({
    ...repositoriesUpdateRepositoryMutation(),
    onSuccess: async (updated) => {
      await queryClient.invalidateQueries()
      reset({
        ...mergeFormValues(updated),
        name: updated.name,
        description: updated.description ?? "",
        default_branch: updated.default_branch ?? "main",
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

  return {
    user,
    deleteOpen,
    setDeleteOpen,
    confirmation,
    setConfirmation,
    data,
    isPending,
    isError,
    refetch,
    branches,
    register,
    control,
    handleSubmit,
    errors,
    isDirty,
    update,
    remove,
  }
}

export const RepositorySettings = ({ owner, repo }: { owner: string; repo: string }) => {
  const {
    user,
    deleteOpen,
    setDeleteOpen,
    confirmation,
    setConfirmation,
    data,
    isPending,
    isError,
    refetch,
    branches,
    register,
    control,
    handleSubmit,
    errors,
    isDirty,
    update,
    remove,
  } = useRepositorySettings({ owner, repo })
  if (isPending) return <RepositoryLoading label="Loading repository settings" />
  if (isError || !data) return <RepositoryError message="Unable to load settings." retry={() => refetch()} />
  if (!user || (user.name.toLowerCase() !== owner.toLowerCase() && !user.is_superuser))
    return <RepositoryError message="Only the repository owner or an administrator can change these settings." />
  const fullName = `${owner}/${repo}`
  const branchOptions = () =>
    (branches?.length ? branches : [{ name: data.default_branch ?? "main" }]).map((branch) => ({
      value: branch.name,
      label: branch.name,
    }))
  const renderSettingsForm = () => (
    <section id="basic-settings" className="overflow-hidden rounded border bg-card">
      <h3 className="border-b bg-secondary px-4 py-3 text-xl font-semibold">Basic settings</h3>
      <form onSubmit={handleSubmit((body) => update.mutate({ path: { owner, repo }, body }))} className="space-y-4 p-4">
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
          <Controller
            control={control}
            name="default_branch"
            render={function renderDefaultBranch({ field }) {
              return (
                <SelectField
                  id="default-branch"
                  aria-label="Default branch"
                  name={field.name}
                  ref={field.ref}
                  value={field.value ?? ""}
                  onValueChange={field.onChange}
                  onBlur={field.onBlur}
                  options={branchOptions()}
                  aria-invalid={Boolean(errors.default_branch)}
                />
              )
            }}
          />
          {errors.default_branch && <p className="text-sm text-destructive">{errors.default_branch.message}</p>}
          <p className="mt-1 text-xs text-muted-foreground">The branch shown when visitors open the repository.</p>
        </div>
        <fieldset id="merge-settings" className="space-y-5 border-t border-border pt-5">
          <legend className="pt-5 text-lg font-semibold">Pull requests</legend>
          <p className="text-sm text-muted-foreground">
            Choose the available merge methods and their commit messages. Disabling all methods prevents merging.
          </p>
          {mergeMethods.map((method) => (
            <div key={method.enabled} className="space-y-2 rounded-md border border-border p-4">
              <div className="flex items-center gap-2">
                <Controller
                  control={control}
                  name={method.enabled}
                  render={({ field }) => (
                    <Checkbox
                      id={method.enabled}
                      checked={field.value}
                      onCheckedChange={(checked) => field.onChange(checked === true)}
                      onBlur={field.onBlur}
                      ref={field.ref}
                    />
                  )}
                />
                <Label htmlFor={method.enabled}>{method.label}</Label>
              </div>
              <p className="text-sm text-muted-foreground">{method.description}</p>
              <Label htmlFor={method.message} appearance="field">
                {method.label} message
              </Label>
              <Controller
                control={control}
                name={method.message}
                render={({ field }) => (
                  <SelectField
                    id={method.message}
                    aria-label={`${method.label} message`}
                    value={field.value}
                    onValueChange={field.onChange}
                    options={messageOptions}
                  />
                )}
              />
            </div>
          ))}
          <div className="flex items-start gap-2">
            <Controller
              control={control}
              name="delete_branch_on_merge"
              render={({ field }) => (
                <Checkbox
                  id="delete-branch-on-merge"
                  checked={field.value}
                  onCheckedChange={(checked) => field.onChange(checked === true)}
                  onBlur={field.onBlur}
                  ref={field.ref}
                />
              )}
            />
            <div>
              <Label htmlFor="delete-branch-on-merge">Automatically delete the PR branch after merging</Label>
              <p className="mt-1 text-sm text-muted-foreground">
                The default branch is kept. The PR’s files, commits and review threads remain available.
              </p>
            </div>
          </div>
        </fieldset>
        <p className="text-sm text-muted-foreground">Visibility: {data.is_private ? "Private" : "Public"}</p>
        <LoadingButton type="submit" loading={update.isPending} disabled={!isDirty || remove.isPending}>
          Save settings
        </LoadingButton>
      </form>
    </section>
  )

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
          <ExternalLink href="#merge-settings" appearance="settings">
            <GitMerge className="size-4 shrink-0" aria-hidden="true" />
            Pull requests
          </ExternalLink>
          <ExternalLink href="#danger-zone" appearance="settingsDanger">
            <Trash2 className="size-4 shrink-0" aria-hidden="true" />
            Danger zone
          </ExternalLink>
        </nav>
      </aside>
      <div className="min-w-0 space-y-6">
        {renderSettingsForm()}
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
