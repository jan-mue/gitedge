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
            <FormField
              control={form.control}
              name="access"
              render={({ field, fieldState }) => (
                <FormItem>
                  <FormLabel>Git access</FormLabel>
                  <FormControl>
                    <SelectField
                      name={field.name}
                      ref={field.ref}
                      value={field.value}
                      onValueChange={field.onChange}
                      onBlur={field.onBlur}
                      disabled={busy}
                      aria-invalid={fieldState.invalid}
                      options={[
                        { value: "read", label: "Read — clone and fetch" },
                        { value: "write", label: "Read and write — clone, fetch, and push" },
                      ]}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="expiry"
              render={({ field, fieldState }) => (
                <FormItem>
                  <FormLabel>Expiration</FormLabel>
                  <FormControl>
                    <SelectField
                      name={field.name}
                      ref={field.ref}
                      value={field.value}
                      onValueChange={field.onChange}
                      onBlur={field.onBlur}
                      disabled={busy}
                      aria-invalid={fieldState.invalid}
                      options={[
                        { value: "30", label: "30 days" },
                        { value: "90", label: "90 days" },
                        { value: "365", label: "1 year" },
                        { value: "never", label: "No expiration" },
                      ]}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <div className="flex gap-2 sm:col-span-2">
              <LoadingButton variant="success" type="submit" loading={busy} disabled={Boolean(issued)}>
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
                      variant="repository"
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
