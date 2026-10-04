import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { GitBranch } from "lucide-react"
import { Suspense } from "react"

import { RepositoriesService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import PendingItems from "@/components/Pending/PendingItems"
import CreateRepository from "@/components/Repositories/CreateRepository"
import { columns } from "@/components/Repositories/columns"

function getRepositoriesQueryOptions() {
  return {
    queryFn: async () => (await RepositoriesService.listRepositories()).data,
    queryKey: ["repositories"],
  }
}

export const Route = createFileRoute("/_layout/repositories")({
  component: Repositories,
  head: () => ({
    meta: [
      {
        title: "Repositories - GitEdge",
      },
    ],
  }),
})

function RepositoriesTableContent() {
  const { data: repositories } = useSuspenseQuery(getRepositoriesQueryOptions())

  if (repositories.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <GitBranch className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">No repositories yet</h3>
        <p className="text-muted-foreground">Create a repository or push one to get started</p>
      </div>
    )
  }

  return <DataTable columns={columns} data={repositories.data} />
}

function RepositoriesTable() {
  return (
    <Suspense fallback={<PendingItems />}>
      <RepositoriesTableContent />
    </Suspense>
  )
}

function Repositories() {
  return (
    <div className="container mx-auto flex max-w-7xl flex-col gap-6 px-4 py-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Repositories</h1>
          <p className="text-muted-foreground">View and manage your Git repositories</p>
        </div>
        <CreateRepository />
      </div>
      <RepositoriesTable />
    </div>
  )
}
