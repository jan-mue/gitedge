import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"
import type { PersonalAccessTokenCreate, PersonalAccessTokenIssued, PersonalAccessTokenPublic } from "@/client"
import {
  personalAccessTokensCreateTokenMutation,
  personalAccessTokensListTokensOptions,
  personalAccessTokensRevokeTokenMutation,
  personalAccessTokensRotateTokenMutation,
} from "@/client/@tanstack/react-query.gen"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const schema = z.object({
  name: z.string().trim().min(1, "Enter a token name").max(120),
  access: z.enum(["read", "write"]),
  expiry: z.enum(["30", "90", "365", "never"]),
})
type TokenForm = z.infer<typeof schema>

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
  const form = useForm<TokenForm>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", access: "read", expiry: "30" },
  })
  const showIssued = async (token: PersonalAccessTokenIssued) => {
    setIssued(token)
    setRotating(null)
    form.reset({ name: "", access: "read", expiry: "30" })
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
      scopes: values.access === "write" ? ["git:read", "git:write"] : ["git:read"],
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
          Use your username and a token as the password when Git asks for credentials. Tokens grant only the selected
          Git operations, within your existing repository access.
        </p>
      </div>
      {issued && (
        <section className="space-y-3 rounded border border-primary p-4" aria-label="New token">
          <h4 className="font-medium">Save your new token</h4>
          <p className="text-sm">Copy it now. The full token will not be shown again.</p>
          <Input aria-label="New personal access token" value={issued.token} readOnly autoComplete="off" />
          <div className="flex gap-2">
            <Button
              variant="outline"
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
        </section>
      )}
      <section className="rounded border bg-card p-4">
        <h4 className="mb-3 font-medium">{rotating ? `Replace ${rotating.name}` : "Create a token"}</h4>
        {rotating && (
          <p className="mb-3 text-sm text-muted-foreground">
            The old token will be revoked when its replacement is created.
          </p>
        )}
        <form onSubmit={form.handleSubmit(submit)} className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label htmlFor="pat-name" className="mb-1 block text-sm font-medium">
              Token name
            </label>
            <Input
              id="pat-name"
              {...form.register("name")}
              aria-invalid={Boolean(form.formState.errors.name)}
              placeholder="Work laptop"
            />
            {form.formState.errors.name && (
              <p className="text-sm text-destructive" role="alert">
                {form.formState.errors.name.message}
              </p>
            )}
          </div>
          <div>
            <label htmlFor="pat-access" className="mb-1 block text-sm font-medium">
              Git access
            </label>
            <select
              id="pat-access"
              {...form.register("access")}
              className="w-full rounded border bg-background px-3 py-2 text-sm"
            >
              <option value="read">Read — clone and fetch</option>
              <option value="write">Read and write — clone, fetch, and push</option>
            </select>
          </div>
          <div>
            <label htmlFor="pat-expiry" className="mb-1 block text-sm font-medium">
              Expiration
            </label>
            <select
              id="pat-expiry"
              {...form.register("expiry")}
              className="w-full rounded border bg-background px-3 py-2 text-sm"
            >
              <option value="30">30 days</option>
              <option value="90">90 days</option>
              <option value="365">1 year</option>
              <option value="never">No expiration</option>
            </select>
          </div>
          <div className="flex gap-2 sm:col-span-2">
            <LoadingButton type="submit" loading={busy} disabled={Boolean(issued)}>
              {rotating ? "Create replacement" : "Create token"}
            </LoadingButton>
            {rotating && (
              <Button
                type="button"
                variant="outline"
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
      </section>
      <section aria-label="Your tokens">
        <h4 className="mb-3 font-medium">Your tokens</h4>
        {tokens.isPending ? (
          <p role="status">Loading tokens…</p>
        ) : tokens.isError ? (
          <div role="alert">
            <p>Unable to load tokens.</p>
            <Button variant="outline" onClick={() => tokens.refetch()}>
              Retry
            </Button>
          </div>
        ) : !tokens.data.length ? (
          <p className="text-sm text-muted-foreground">No personal access tokens.</p>
        ) : (
          <ul className="divide-y rounded border bg-card">
            {tokens.data.map((token) => (
              <li key={token.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
                <div>
                  <p className="font-medium">
                    {token.name} <span className="ml-2 text-xs text-muted-foreground">{tokenStatus(token)}</span>
                  </p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Ending in {token.secret_last4} · {token.scopes.includes("git:write") ? "Read and write" : "Read"}
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
                      variant="outline"
                      disabled={busy || Boolean(issued)}
                      onClick={() => {
                        setRotating(token)
                        form.reset({
                          name: token.name,
                          access: token.scopes.includes("git:write") ? "write" : "read",
                          expiry: "30",
                        })
                      }}
                    >
                      Rotate
                    </Button>
                    <Button
                      variant="destructive"
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
