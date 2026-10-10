import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import {
  repositoriesCreateRepositoryMutation,
  repositoriesListRepositoriesQueryKey,
} from "@/client/@tanstack/react-query.gen"
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

const formSchema = z.object({
  owner: z
    .string()
    .min(1, { message: "Owner is required" })
    .regex(/^[a-zA-Z0-9_-]+$/, {
      message: "Owner must only contain letters, numbers, hyphens, and underscores",
    }),
  name: z
    .string()
    .min(1, { message: "Repository name is required" })
    .regex(/^[a-zA-Z0-9._-]+$/, {
      message: "Repository name must only contain letters, numbers, dots, hyphens, and underscores",
    }),
})

type FormData = z.infer<typeof formSchema>

const CreateRepository = () => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      owner: "",
      name: "",
    },
  })

  const mutation = useMutation({
    ...repositoriesCreateRepositoryMutation(),
    onSuccess: () => {
      showSuccessToast("Repository created successfully")
      form.reset()
      setIsOpen(false)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: repositoriesListRepositoriesQueryKey() })
    },
  })

  const onSubmit = (data: FormData) => {
    mutation.mutate({ body: data })
  }

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button data-testid="create-repository-button">
          <Plus className="mr-2" />
          New Repository
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create Repository</DialogTitle>
          <DialogDescription>Create a new empty Git repository.</DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)}>
            <div className="grid gap-4 py-4">
              <FormField
                control={form.control}
                name="owner"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      Owner <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input placeholder="owner" type="text" data-testid="create-repo-owner" {...field} required />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      Repository Name <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input placeholder="my-repo" type="text" data-testid="create-repo-name" {...field} required />
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
              <LoadingButton type="submit" loading={mutation.isPending} data-testid="create-repo-submit">
                Create
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default CreateRepository
