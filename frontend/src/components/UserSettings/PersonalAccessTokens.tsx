import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { type Control, useForm } from "react-hook-form"
import { z } from "zod"
import type {
  PersonalAccessTokenCreate,
  PersonalAccessTokenIssued,
  PersonalAccessTokenPublic,
  TokenScope,
} from "@/client"
import {
  personalAccessTokensCreateTokenMutation,
  personalAccessTokensListTokensOptions,
  personalAccessTokensRepositoryOptionsOptions,
  personalAccessTokensRevokeTokenMutation,
  personalAccessTokensRotateTokenMutation,
} from "@/client/@tanstack/react-query.gen"
import {
  Alert,
  AlertDescription,
  AlertTitle,
  Badge,
  Button,
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
  Input,
  LoadingButton,
  SelectField,
} from "@/components/design-system"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import { TokenChoices } from "./TokenChoices"

const schema = z.object({
  name: z.string().trim().min(1, "Enter a token name").max(120),
  scopes: z.array(z.custom<TokenScope>()).min(1, "Select at least one operation"),
  repository_ids: z.array(z.string()).min(1, "Select at least one repository"),
  expiry: z.enum(["30", "90", "365", "never"]),
})
type TokenForm = z.infer<typeof schema>

const TokenSelect = ({
  control,
  name,
  label,
  busy,
  options,
}: {
  control: Control<TokenForm>
  name: "expiry"
  label: string
  busy: boolean
  options: { value: string; label: string }[]
}) => (
  <FormField
    control={control}
    name={name}
    render={({ field, fieldState }) => (
      <FormItem>
        <FormLabel>{label}</FormLabel>
        <FormControl>
          <SelectField
            {...field}
            onValueChange={field.onChange}
            disabled={busy}
            aria-invalid={fieldState.invalid}
            options={options}
          />
        </FormControl>
        <FormMessage />
      </FormItem>
    )}
  />
)

const scopeGroups: { label: string; options: { value: TokenScope; label: string }[] }[] = [
  {
    label: "Actions",
    options: [
      { value: "actions:read", label: "Read workflow runs and logs" },
      { value: "actions:write", label: "Dispatch and cancel workflows" },
    ],
  },
  {
    label: "Repository",
    options: [
      { value: "repository:read", label: "Read repository contents and discussions" },
      { value: "repository:write", label: "Rename repositories and update settings" },
      { value: "repository:delete", label: "Delete repositories" },
    ],
  },
  {
    label: "Git commits",
    options: [
      { value: "git:read", label: "Clone and fetch commits" },
      { value: "git:write", label: "Push commits (includes clone and fetch)" },
    ],
  },
  {
    label: "Issues",
    options: [{ value: "issues:write", label: "Create and update issues" }],
  },
  {
    label: "Pull requests",
    options: [
      { value: "pull_requests:write", label: "Create and update pull requests" },
      { value: "pull_requests:merge", label: "Merge pull requests" },
    ],
  },
  {
    label: "Comments and reactions",
    options: [{ value: "comments:write", label: "Create, edit, and delete comments and reactions" }],
  },
  {
    label: "Reviews",
    options: [{ value: "reviews:write", label: "Submit reviews and manage review drafts" }],
  },
  {
    label: "Releases",
    options: [{ value: "releases:write", label: "Create and update releases" }],
  },
]
const scopeOptions = scopeGroups.flatMap((group) => group.options)
const defaults: TokenForm = { name: "", scopes: ["repository:read"], repository_ids: [], expiry: "30" }

const tokenStatus = (token: PersonalAccessTokenPublic) => {
  if (token.revoked_at) return "Revoked"
  if (token.expires_at && new Date(token.expires_at) <= new Date()) return "Expired"
  return "Active"
}

const PersonalAccessTokens = () => {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [issued, setIssued] = useState<PersonalAccessTokenIssued | null>(null)
  const [rotating, setRotating] = useState<PersonalAccessTokenPublic | null>(null)
  const tokens = useQuery(personalAccessTokensListTokensOptions())
  const repositories = useQuery(personalAccessTokensRepositoryOptionsOptions())
  const form = useForm<TokenForm>({
    resolver: zodResolver(schema),
    defaultValues: defaults,
  })
  const showIssued = async (token: PersonalAccessTokenIssued) => {
    setIssued(token)
    setRotating(null)
    form.reset(defaults)
    await queryClient.invalidateQueries({ queryKey: personalAccessTokensListTokensOptions().queryKey })
  }
  const create = useMutation({
    ...personalAccessTokensCreateTokenMutation(),
    gcTime: 0,
    onSuccess: showIssued,
    onError: handleError.bind(showErrorToast),
  })
  const rotate = useMutation({
    ...personalAccessTokensRotateTokenMutation(),
    gcTime: 0,
    onSuccess: showIssued,
    onError: handleError.bind(showErrorToast),
  })
  const revoke = useMutation({
    ...personalAccessTokensRevokeTokenMutation(),
    onSuccess: async () => {
      showSuccessToast("Token revoked")
      await queryClient.invalidateQueries({ queryKey: personalAccessTokensListTokensOptions().queryKey })
    },
    onError: handleError.bind(showErrorToast),
  })
  const busy = create.isPending || rotate.isPending || revoke.isPending
  const dismiss = () => {
    setIssued(null)
    create.reset()
    rotate.reset()
  }
  const submit = (values: TokenForm) => {
    const body: PersonalAccessTokenCreate = {
      name: values.name,
      scopes: values.scopes,
      repository_ids: values.repository_ids,
      expires_at:
        values.expiry === "never" ? null : new Date(Date.now() + Number(values.expiry) * 86400000).toISOString(),
    }
    if (rotating) rotate.mutate({ path: { token_id: rotating.id }, body })
    else create.mutate({ body })
  }
  return (
    <div className="max-w-3xl space-y-6 py-4">
      <div>
        <h3 className="text-lg font-semibold">Personal access tokens</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Choose exactly which repositories and operations each token can access. Tokens also require your account’s
          current repository permissions. Use a token with Git or as a Bearer credential for the repository API.
        </p>
      </div>
      {issued && (
        <Alert aria-label="New token">
          <AlertTitle>Save your new token</AlertTitle>
          <AlertDescription>Copy it now. The full token will not be shown again.</AlertDescription>
          <div className="my-3">
            <Input aria-label="New personal access token" value={issued.token} readOnly autoComplete="off" />
          </div>
          <div className="flex gap-2">
            <Button
              variant="repository"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(issued.token)
                  showSuccessToast("Token copied")
                } catch (error) {
                  handleError.call(showErrorToast, error)
                }
              }}
            >
              Copy token
            </Button>
            <Button onClick={dismiss}>I've saved my token</Button>
          </div>
        </Alert>
      )}
      <section className="rounded border bg-card p-4">
        <h4 className="mb-3 font-medium">{rotating ? `Replace ${rotating.name}` : "Create a token"}</h4>
        {rotating && (
          <p className="mb-3 text-sm text-muted-foreground">
            The old token will be revoked when its replacement is created.
          </p>
        )}
        <Form {...form}>
          <form onSubmit={form.handleSubmit(submit)} className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <FormField
                control={form.control}
                name="name"
                render={({ field, fieldState }) => (
                  <FormItem>
                    <FormLabel>Token name</FormLabel>
                    <FormControl>
                      <Input {...field} aria-invalid={fieldState.invalid} placeholder="Work laptop" disabled={busy} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <div className="sm:col-span-2">
              <FormField
                control={form.control}
                name="repository_ids"
                render={({ field }) => (
                  <FormItem>
                    {repositories.isPending ? (
                      <p role="status">Loading repositories…</p>
                    ) : repositories.isError ? (
                      <Alert variant="destructive">
                        <AlertDescription>Unable to load repositories.</AlertDescription>
                        <Button type="button" onClick={() => repositories.refetch()}>
                          Retry
                        </Button>
                      </Alert>
                    ) : (
                      <TokenChoices
                        label="Repositories"
                        searchable
                        options={repositories.data.map((repository) => ({
                          value: repository.id,
                          label: `${repository.owner}/${repository.name}`,
                        }))}
                        selected={field.value}
                        onChange={field.onChange}
                        disabled={busy}
                      />
                    )}
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <div className="sm:col-span-2">
              <FormField
                control={form.control}
                name="scopes"
                render={({ field }) => (
                  <FormItem>
                    <fieldset disabled={busy} className="space-y-4">
                      <legend className="mb-3 text-sm font-medium">Allowed operations</legend>
                      <div className="grid gap-4 sm:grid-cols-2">
                        {scopeGroups.map((group) => (
                          <TokenChoices
                            key={group.label}
                            label={group.label}
                            options={group.options}
                            selected={field.value}
                            onChange={field.onChange}
                            disabled={busy}
                          />
                        ))}
                      </div>
                    </fieldset>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <TokenSelect
              control={form.control}
              name="expiry"
              label="Expiration"
              busy={busy}
              options={[
                { value: "30", label: "30 days" },
                { value: "90", label: "90 days" },
                { value: "365", label: "1 year" },
                { value: "never", label: "No expiration" },
              ]}
            />
            <div className="flex gap-2 sm:col-span-2">
              <LoadingButton
                variant="success"
                type="submit"
                loading={busy}
                disabled={Boolean(issued) || !repositories.data?.length}
              >
                {rotating ? "Create replacement" : "Create token"}
              </LoadingButton>
              {rotating && (
                <Button
                  type="button"
                  variant="repository"
                  disabled={busy}
                  onClick={() => {
                    setRotating(null)
                    form.reset()
                  }}
                >
                  Cancel
                </Button>
              )}
            </div>
          </form>
        </Form>
      </section>
      <section aria-label="Your tokens">
        <h4 className="mb-3 font-medium">Your tokens</h4>
        {tokens.isPending ? (
          <p role="status">Loading tokens…</p>
        ) : tokens.isError ? (
          <Alert variant="destructive">
            <AlertDescription>Unable to load tokens.</AlertDescription>
            <div className="mt-3">
              <Button variant="repository" onClick={() => tokens.refetch()}>
                Retry
              </Button>
            </div>
          </Alert>
        ) : !tokens.data.length ? (
          <p className="text-sm text-muted-foreground">No personal access tokens.</p>
        ) : (
          <ul className="divide-y rounded border bg-card">
            {tokens.data.map((token) => (
              <li key={token.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
                <div>
                  <p className="font-medium">
                    {token.name}{" "}
                    <Badge
                      variant={
                        tokenStatus(token) === "Active"
                          ? "success"
                          : tokenStatus(token) === "Expired"
                            ? "warning"
                            : "secondary"
                      }
                    >
                      {tokenStatus(token)}
                    </Badge>
                  </p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Ending in {token.secret_last4} · {token.repository_ids.length} repositories
                  </p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {token.scopes
                      .map((scope) => scopeOptions.find((option) => option.value === scope)?.label ?? scope)
                      .join(" · ")}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {token.repository_ids
                      .map((id) => {
                        const repository = repositories.data?.find((item) => item.id === id)
                        return repository ? `${repository.owner}/${repository.name}` : "Unavailable repository"
                      })
                      .join(", ")}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Created {new Date(token.created_at).toLocaleDateString()} ·{" "}
                    {token.expires_at ? `Expires ${new Date(token.expires_at).toLocaleDateString()}` : "No expiration"}{" "}
                    · {token.last_used_at ? `Last used ${new Date(token.last_used_at).toLocaleString()}` : "Never used"}
                  </p>
                  {token.revoked_reason && <p className="text-xs text-muted-foreground">{token.revoked_reason}</p>}
                </div>
                {!token.revoked_at && (
                  <div className="flex gap-2">
                    <Button
                      variant="repository"
                      disabled={busy || Boolean(issued)}
                      onClick={() => {
                        setRotating(token)
                        form.reset({
                          name: token.name,
                          scopes: token.scopes,
                          repository_ids: token.repository_ids.filter((id) =>
                            repositories.data?.some((repository) => repository.id === id),
                          ),
                          expiry: "30",
                        })
                      }}
                    >
                      Rotate
                    </Button>
                    <Button
                      variant="dangerOutline"
                      disabled={busy}
                      onClick={() => {
                        if (rotating?.id === token.id) setRotating(null)
                        revoke.mutate({ path: { token_id: token.id }, body: { reason: "Revoked in account settings" } })
                      }}
                    >
                      Revoke
                    </Button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

export default PersonalAccessTokens
