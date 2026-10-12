import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { GitFork } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"
import {
  forksForkRepositoryMutation,
  forksListForksOptions,
  forksListForksQueryKey,
  repositoriesListRepositoriesQueryKey,
} from "@/client/@tanstack/react-query.gen"
import {
  Button,
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
  Input,
  LoadingButton,
  Link as RouterLink,
} from "@/components/design-system"
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
    ...forksListForksOptions({ path: { owner, repo } }),
  })

  const mutation = useMutation({
    ...forksForkRepositoryMutation(),
    onSuccess: (fork) => {
      showSuccessToast("Repository forked successfully")
      form.reset()
      setIsOpen(false)
      queryClient.invalidateQueries({ queryKey: forksListForksQueryKey({ path: { owner, repo } }) })
      queryClient.invalidateQueries({ queryKey: repositoriesListRepositoriesQueryKey() })
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
          <Button type="button" data-testid="fork-button" variant="repository" size="compact" shape="start">
            <GitFork className="h-3.5 w-3.5" />
            Fork
          </Button>
        </DialogTrigger>
        <RouterLink to="/$owner/$repo/forks" params={{ owner, repo }} data-testid="fork-count" appearance="count">
          {forks?.count ?? 0}
        </RouterLink>
      </div>
      <DialogContent appearance="compact">
        <DialogHeader>
          <DialogTitle>Fork repository</DialogTitle>
          <DialogDescription>Create a copy of {`${owner}/${repo}`} in your account.</DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit((data) => mutation.mutate({ path: { owner, repo }, body: data }))}>
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
                <Button variant="repository" disabled={mutation.isPending}>
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
