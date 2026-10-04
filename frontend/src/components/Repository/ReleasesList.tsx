import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Check, Plus, Tag } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { type ReleasePublic, ReleasesService } from "@/client"
import { Badge } from "@/components/ui/badge"
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

interface ReleasesListProps {
  owner: string
  repo: string
}

const formSchema = z.object({
  tag_name: z.string().min(1, { message: "Tag name is required" }),
  name: z.string().optional(),
  body: z.string().optional(),
  is_prerelease: z.boolean().optional(),
})

type FormData = z.infer<typeof formSchema>

const ReleaseCard = ({ release }: { release: ReleasePublic }) => (
  <div className="border border-border rounded-lg bg-card px-4 py-3" data-testid={`release-${release.tag_name}`}>
    <div className="flex items-center gap-2">
      <Tag className="w-4 h-4 text-muted-foreground" />
      <span className="font-mono text-sm font-medium text-foreground">{release.tag_name}</span>
      {release.is_prerelease && <Badge variant="secondary">Pre-release</Badge>}
      {release.published_at && (
        <span className="ml-auto text-xs text-muted-foreground">
          {new Date(release.published_at).toLocaleDateString()}
        </span>
      )}
    </div>
    {release.name && <p className="mt-2 text-sm font-medium text-foreground">{release.name}</p>}
    {release.body && <p className="mt-1 text-sm text-muted-foreground whitespace-pre-wrap">{release.body}</p>}
    {release.author_username && <p className="mt-2 text-xs text-muted-foreground">by {release.author_username}</p>}
  </div>
)

const ReleasesList = ({ owner, repo }: ReleasesListProps) => {
  const repoPath = `${owner}/${repo}.git`
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [isOpen, setIsOpen] = useState(false)

  const { data: releasesData } = useQuery({
    queryKey: ["releases", repoPath],
    queryFn: async () => (await ReleasesService.listReleases({ path: { path: repoPath } })).data,
  })

  const { data: tagsData } = useQuery({
    queryKey: ["tags", repoPath],
    queryFn: async () => (await ReleasesService.listTags({ path: { path: repoPath } })).data,
  })

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: { tag_name: "", name: "", body: "" },
  })

  const mutation = useMutation({
    mutationFn: (data: FormData) =>
      ReleasesService.createRelease({
        path: { path: repoPath },
        body: {
          tag_name: data.tag_name,
          name: data.name || null,
          body: data.body || null,
          is_prerelease: data.is_prerelease ?? false,
        },
      }),
    onSuccess: () => {
      showSuccessToast("Release created successfully")
      form.reset()
      setIsOpen(false)
      queryClient.invalidateQueries({ queryKey: ["releases", repoPath] })
    },
    onError: handleError.bind(showErrorToast),
  })

  const releases = releasesData?.data ?? []
  const tags = tagsData?.data ?? []

  return (
    <div className="space-y-6" data-testid="releases-list">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-foreground">
          {releases.length} {releases.length === 1 ? "release" : "releases"}
        </h2>
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
          <DialogTrigger asChild>
            <Button size="sm" variant="outline" data-testid="new-release-button">
              <Plus className="w-3.5 h-3.5" />
              New release
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>Create release</DialogTitle>
              <DialogDescription>Create a release tied to a Git tag.</DialogDescription>
            </DialogHeader>
            <Form {...form}>
              <form onSubmit={form.handleSubmit((data) => mutation.mutate(data))}>
                <div className="grid gap-4 py-4">
                  <FormField
                    control={form.control}
                    name="tag_name"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>
                          Tag name <span className="text-destructive">*</span>
                        </FormLabel>
                        <FormControl>
                          <Input placeholder="v1.0.0" data-testid="release-tag-input" {...field} required />
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
                        <FormLabel>Release title</FormLabel>
                        <FormControl>
                          <Input placeholder="Release title" data-testid="release-name-input" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="body"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Description</FormLabel>
                        <FormControl>
                          <textarea
                            id="release-body"
                            rows={5}
                            placeholder="Release notes"
                            data-testid="release-body-input"
                            className="w-full px-3 py-2 text-sm bg-secondary border border-border rounded text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary resize-y"
                            {...field}
                          />
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
                  <LoadingButton type="submit" loading={mutation.isPending} data-testid="release-submit">
                    Create release
                  </LoadingButton>
                </DialogFooter>
              </form>
            </Form>
          </DialogContent>
        </Dialog>
      </div>

      {releases.length > 0 ? (
        <div className="space-y-3">
          {releases.map((release) => (
            <ReleaseCard key={release.id} release={release} />
          ))}
        </div>
      ) : (
        <div className="py-12 text-center text-sm text-muted-foreground">No releases yet.</div>
      )}

      {tags.length > 0 && (
        <section className="border border-border rounded-lg overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-2.5 bg-secondary border-b border-border">
            <Check className="w-4 h-4 text-muted-foreground" />
            <h3 className="text-sm font-semibold text-foreground">{tags.length} tags</h3>
          </div>
          {tags.map((tag) => (
            <div
              key={tag.name}
              className="flex items-center justify-between px-4 py-3 border-b border-border last:border-b-0"
            >
              <span className="font-mono text-sm text-foreground">{tag.name}</span>
              <span className="font-mono text-xs text-muted-foreground">{tag.commit_sha.slice(0, 10)}</span>
            </div>
          ))}
        </section>
      )}
    </div>
  )
}

export default ReleasesList
