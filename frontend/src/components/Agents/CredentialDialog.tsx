import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { KeyRound, Trash2 } from "lucide-react"
import { useForm } from "react-hook-form"
import { z } from "zod"
import {
  agentsCredentialsOptions,
  agentsCredentialsQueryKey,
  agentsProvidersOptions,
  agentsRemoveCredentialsMutation,
  agentsSaveCredentialsMutation,
} from "@/client/@tanstack/react-query.gen"
import {
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Input,
  Label,
  SelectField,
} from "@/components/design-system"
import { extractErrorMessage } from "@/utils"

const credentialSchema = z.object({
  provider: z.string().min(1, "Select a provider"),
  label: z.string().trim().min(1, "Enter a label").max(200),
  secret: z.string().min(1, "Enter a key or import a connection file").max(100000),
})
type Values = z.infer<typeof credentialSchema>

export const CredentialDialog = ({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) => {
  const query = useQueryClient()
  const providers = useQuery({ ...agentsProvidersOptions(), enabled: open })
  const connections = useQuery({ ...agentsCredentialsOptions(), enabled: open })
  const form = useForm<Values>({
    resolver: zodResolver(credentialSchema),
    defaultValues: { provider: "openai", label: "", secret: "" },
  })
  const provider = form.watch("provider")
  const oauth = providers.data?.find((value) => value.provider === provider)?.auth === "chatgpt"
  const save = useMutation({
    ...agentsSaveCredentialsMutation(),
    onSuccess: async () => {
      form.reset({ provider, label: "", secret: "" })
      await query.invalidateQueries({ queryKey: agentsCredentialsQueryKey() })
    },
  })
  const remove = useMutation({
    ...agentsRemoveCredentialsMutation(),
    onSuccess: () => query.invalidateQueries({ queryKey: agentsCredentialsQueryKey() }),
  })
  const close = (value: boolean) => {
    if (!value) form.reset()
    onOpenChange(value)
  }
  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent appearance="access">
        <DialogHeader>
          <DialogTitle>AI credentials</DialogTitle>
          <DialogDescription>
            Connect your account. Credentials are encrypted in GitEdge and stay in the backend.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          {connections.data?.map((connection) => (
            <div
              key={connection.provider}
              className="flex items-center justify-between rounded-lg border border-border p-3"
            >
              <div className="flex items-center gap-3">
                <KeyRound className="size-4 text-muted-foreground" />
                <div>
                  <p className="text-sm font-medium">{connection.label}</p>
                  <p className="text-xs text-muted-foreground">
                    {providers.data?.find((value) => value.provider === connection.provider)?.label ??
                      connection.provider}
                  </p>
                </div>
              </div>
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label={`Remove ${connection.label}`}
                disabled={remove.isPending}
                onClick={() => remove.mutate({ path: { provider: connection.provider } })}
              >
                <Trash2 className="size-4" />
              </Button>
            </div>
          ))}
        </div>
        <form
          className="space-y-4"
          onSubmit={form.handleSubmit(({ provider, label, secret }) =>
            save.mutate({ path: { provider }, body: { label, secret } }),
          )}
        >
          <div className="space-y-2">
            <Label htmlFor="agent-provider">Provider</Label>
            <SelectField
              id="agent-provider"
              value={provider}
              onValueChange={(value) => {
                form.setValue("provider", value)
                form.setValue("secret", "")
              }}
              options={(providers.data ?? []).map((value) => ({ value: value.provider, label: value.label }))}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="agent-credential-label">Connection label</Label>
            <Input
              id="agent-credential-label"
              autoComplete="off"
              {...form.register("label")}
              placeholder="My coding account"
            />
          </div>
          {oauth ? (
            <div className="space-y-3 rounded-lg border border-border p-4">
              <p className="text-sm">
                Sign in locally with the PydanticAI helper, then import the connection file. OpenAI requires the sign-in
                callback on your own machine.
              </p>
              <pre className="overflow-auto rounded bg-secondary p-3 text-xs">
                cd backend{`\n`}uv run python -m app.agents.login
              </pre>
              <Label htmlFor="agent-chatgpt-file">ChatGPT connection file</Label>
              <Input
                id="agent-chatgpt-file"
                type="file"
                accept="application/json,.json"
                onChange={async (event) => {
                  const file = event.target.files?.[0]
                  if (file) form.setValue("secret", await file.text(), { shouldValidate: true })
                }}
              />
            </div>
          ) : (
            <div className="space-y-2">
              <Label htmlFor="agent-provider-secret">API key</Label>
              <Input
                id="agent-provider-secret"
                type="password"
                autoComplete="new-password"
                {...form.register("secret")}
              />
            </div>
          )}
          {Object.values(form.formState.errors).map((error) => (
            <p key={error.message} role="alert" className="text-sm text-destructive">
              {error.message}
            </p>
          ))}
          {(save.error ?? remove.error ?? providers.error) && (
            <p role="alert" className="text-sm text-destructive">
              {extractErrorMessage(save.error ?? remove.error ?? providers.error)}
            </p>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => close(false)}>
              Close
            </Button>
            <Button type="submit" loading={save.isPending}>
              Save connection
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
