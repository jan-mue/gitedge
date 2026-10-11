import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { GitBranch } from "lucide-react"
import { Suspense } from "react"
import { repositoriesListRepositoriesOptions } from "@/client/@tanstack/react-query.gen"
import { DataTable } from "@/components/Common/DataTable"
import PendingItems from "@/components/Pending/PendingItems"
import CreateRepository from "@/components/Repositories/CreateRepository"
import { columns } from "@/components/Repositories/columns"
import { EmptyState, Page, PageHeader } from "@/design-system"

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
  const { data: repositories } = useSuspenseQuery(repositoriesListRepositoriesOptions())

  if (repositories.data.length === 0) {
    return (
      <EmptyState
        title="No repositories yet"
        description="Create a repository or push one to get started"
        icon={GitBranch}
      />
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
    <Page>
      <PageHeader
        title="Repositories"
        description="View and manage your Git repositories"
        actions={<CreateRepository />}
      />
      <RepositoriesTable />
    </Page>
  )
}
