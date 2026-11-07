import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"
import { repositoriesListRepositoriesOptions } from "@/client/@tanstack/react-query.gen"
import {
  Button,
  ChoiceInput,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Input,
  Label,
  Textarea,
} from "@/components/design-system"
import { agentApi, type EnvironmentPublic } from "./api"

const environmentSchema = z.object({
  name: z.string().trim().min(1, "Enter a name").max(200),
  repositories: z.array(z.string()).min(1, "Select at least one repository"),
  setup_script: z.string().max(100000),
  instructions: z.string().max(100000),
})
type Values = z.infer<typeof environmentSchema>

export const EnvironmentDialog = ({
  open,
  onOpenChange,
  environment,
  onSaved,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  environment?: EnvironmentPublic
  onSaved: (environment: EnvironmentPublic) => void
}) => {
  const query = useQueryClient()
  const repositories = useQuery({ ...repositoriesListRepositoriesOptions(), enabled: open })
  const form = useForm<Values>({
    resolver: zodResolver(environmentSchema),
    defaultValues: { name: "", repositories: [], setup_script: "", instructions: "" },
  })
  useEffect(() => {
    if (open)
      form.reset(
        environment
          ? {
              name: environment.name,
              repositories: environment.repositories ?? [],
              setup_script: environment.setup_script,
              instructions: environment.instructions,
            }
          : { name: "", repositories: [], setup_script: "", instructions: "" },
      )
  }, [open, environment, form])
  const selected = form.watch("repositories")
  const save = useMutation({
    mutationFn: (values: Values) =>
      environment
        ? agentApi<EnvironmentPublic>(`/environments/${environment.id}`, values, "PUT")
        : agentApi<EnvironmentPublic>("/environments", values),
    onSuccess: async (value) => {
      await query.invalidateQueries({ queryKey: ["agent-environments"] })
      onSaved(value)
      onOpenChange(false)
    },
  })
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent appearance="access">
        <DialogHeader>
          <DialogTitle>{environment ? "Edit environment" : "New environment"}</DialogTitle>
          <DialogDescription>
            Prepare repositories once in a setup chat, then reuse the environment for independent coding chats.
          </DialogDescription>
        </DialogHeader>
        <form className="space-y-5" onSubmit={form.handleSubmit((values) => save.mutate(values))}>
          <div className="space-y-2">
            <Label htmlFor="agent-environment-name">Name</Label>
            <Input id="agent-environment-name" {...form.register("name")} aria-invalid={!!form.formState.errors.name} />
            {form.formState.errors.name && (
              <p role="alert" className="text-sm text-destructive">
                {form.formState.errors.name.message}
              </p>
            )}
          </div>
          <fieldset className="max-h-48 space-y-2 overflow-auto">
            <legend className="mb-2 text-sm font-medium">Repositories</legend>
            {(
              environment?.repositories?.map((name) => ({ owner: name.split("/")[0], name: name.split("/")[1] })) ??
              repositories.data?.data ??
              []
            ).map((repository) => {
              const name = `${repository.owner}/${repository.name}`
              return (
                <label
                  key={name}
                  htmlFor={`environment-repository-${name}`}
                  className="flex items-center gap-2 text-sm"
                >
                  <ChoiceInput
                    id={`environment-repository-${name}`}
                    type="checkbox"
                    disabled={!!environment}
                    checked={selected.includes(name)}
                    onChange={(event) =>
                      form.setValue(
                        "repositories",
                        event.target.checked ? [...selected, name] : selected.filter((value) => value !== name),
                        { shouldValidate: true },
                      )
                    }
                  />
                  {name}
                </label>
              )
            })}
            {repositories.isPending && <p className="text-sm text-muted-foreground">Loading repositories…</p>}
            {repositories.error && (
              <p role="alert" className="text-sm text-destructive">
                Unable to load repositories.
              </p>
            )}
            {form.formState.errors.repositories && (
              <p role="alert" className="text-sm text-destructive">
                {form.formState.errors.repositories.message}
              </p>
            )}
          </fieldset>
          <div className="space-y-2">
            <Label htmlFor="agent-setup-script">Setup script</Label>
            <p className="text-xs text-muted-foreground">
              Leave empty to use the repository’s .gitedge/agents/setup.sh. Changes apply when you start a new setup
              chat.
            </p>
            <Textarea
              id="agent-setup-script"
              rows={6}
              {...form.register("setup_script")}
              placeholder="#!/usr/bin/env bash&#10;set -euo pipefail"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="agent-environment-instructions">Instructions</Label>
            <Textarea
              id="agent-environment-instructions"
              rows={4}
              {...form.register("instructions")}
              placeholder="Project conventions and how to run checks…"
            />
          </div>
          {save.error && (
            <p role="alert" className="text-sm text-destructive">
              {save.error.message}
            </p>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={save.isPending}>
              {environment ? "Save changes" : "Create environment"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
