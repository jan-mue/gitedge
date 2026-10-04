import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link as RouterLink, useNavigate } from "@tanstack/react-router"
import { GitFork } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { ForksService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface ForkButtonProps {
  owner: string
  repo: string
}

const formSchema = z.object({
  name: z
    .string()
    .min(1, { message: "Repository name is required" })
    .regex(/^[a-zA-Z0-9._-]+$/, {
      message: "Repository name must only contain letters, numbers, dots, hyphens, and underscores",
    }),
})

type FormData = z.infer<typeof formSchema>

const ForkButton = ({ owner, repo }: ForkButtonProps) => {
  const repoPath = `${owner}/${repo}.git`
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: { name: repo },
  })

  const { data: forks } = useQuery({
    queryKey: ["forks", repoPath],
    queryFn: async () => (await ForksService.listForks({ path: { path: repoPath } })).data,
  })

  const mutation = useMutation({
    mutationFn: (data: FormData) => ForksService.forkRepository({ path: { path: repoPath }, body: data }),
    onSuccess: (response) => {
      const fork = response.data
      showSuccessToast("Repository forked successfully")
      form.reset()
      setIsOpen(false)
      queryClient.invalidateQueries({ queryKey: ["forks", repoPath] })
      if (fork.owner) {
        navigate({ to: "/$owner/$repo", params: { owner: fork.owner, repo: fork.name } })
      }
    },
    onError: handleError.bind(showErrorToast),
  })

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <div className="flex items-stretch">
        <DialogTrigger asChild>
          <button
            type="button"
            data-testid="fork-button"
            className="flex items-center gap-1.5 rounded-l border border-border bg-secondary px-3 py-1.5 text-sm text-foreground transition-colors hover:bg-accent"
          >
            <GitFork className="h-3.5 w-3.5" />
            Fork
          </button>
        </DialogTrigger>
        <RouterLink
          to="/$owner/$repo/forks"
          params={{ owner, repo }}
          data-testid="fork-count"
          className="flex items-center rounded-r border border-l-0 border-border bg-secondary px-2.5 py-1.5 text-sm text-foreground transition-colors hover:bg-accent"
        >
          {forks?.count ?? 0}
        </RouterLink>
      </div>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Fork repository</DialogTitle>
          <DialogDescription>Create a copy of {`${owner}/${repo}`} in your account.</DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit((data) => mutation.mutate(data))}>
            <div className="grid gap-4 py-4">
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      Repository Name <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input placeholder={repo} type="text" data-testid="fork-repo-name" {...field} required />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline" disabled={mutation.isPending}>
                  Cancel
                </Button>
              </DialogClose>
              <LoadingButton type="submit" loading={mutation.isPending} data-testid="fork-repo-submit">
                Fork
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default ForkButton
