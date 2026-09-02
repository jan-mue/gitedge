import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"

import { RepositoriesService } from "@/client"
import CodeViewer from "@/components/Repositories/CodeViewer"
import RefBadge from "@/components/Repositories/RefBadge"
import RepoBreadcrumbs from "@/components/Repositories/RepoBreadcrumbs"
import RepositoryLayout from "@/components/Repositories/RepositoryLayout"

interface SearchParams {
  ref?: string
  path: string
}

export const Route = createFileRoute("/_layout/$owner/$repo/blob")({
  component: FileViewer,
  validateSearch: (search: Record<string, unknown>): SearchParams => ({
    ref: (search.ref as string) || undefined,
    path: (search.path as string) || "",
  }),
  head: ({ params }) => ({
    meta: [
      {
        title: `File - ${params.owner}/${params.repo} - GitEdge`,
      },
    ],
  }),
})

function BlobContent() {
  const { owner, repo } = Route.useParams()
  const { ref: searchRef, path: filePath } = Route.useSearch()
  const repoPath = owner === "_" ? `${repo}.git` : `${owner}/${repo}.git`

  const { data: file } = useSuspenseQuery({
    queryKey: ["blob", repoPath, searchRef ?? "main", filePath],
    queryFn: async () =>
      (
        await RepositoriesService.getBlob({
          path: { path: repoPath },
          query: { ref: searchRef, file_path: filePath },
        })
      ).data,
  })

  const parentParts = filePath.split("/").filter(Boolean)
  const parentPath =
    parentParts.length > 1 ? parentParts.slice(0, -1).join("/") : ""

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <RepoBreadcrumbs
          owner={owner}
          repo={repo}
          path={filePath}
          searchRef={searchRef}
        />
        <RefBadge gitRef={searchRef ?? "main"} />
      </div>

      <CodeViewer
        file={file}
        backLink={{ owner, repo, searchRef, path: parentPath }}
      />
    </div>
  )
}

function FileViewer() {
  const { owner, repo } = Route.useParams()

  return (
    <RepositoryLayout owner={owner} repo={repo}>
      <BlobContent />
    </RepositoryLayout>
  )
}
