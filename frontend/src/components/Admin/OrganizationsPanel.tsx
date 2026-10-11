import { useSuspenseQuery } from "@tanstack/react-query"
import { Building2 } from "lucide-react"
import { Suspense } from "react"
import { organizationsListOrganizationsOptions } from "@/client/@tanstack/react-query.gen"
import PendingUsers from "@/components/Pending/PendingUsers"

function OrganizationsContent() {
  const { data: organizations } = useSuspenseQuery(
    organizationsListOrganizationsOptions({ query: { offset: 0, limit: 100 } }),
  )

  if (organizations.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border py-16 text-center">
        <Building2 className="mb-3 h-10 w-10 text-muted-foreground opacity-60" />
        <h3 className="text-lg font-semibold text-foreground">No organizations yet</h3>
        <p className="mt-1 max-w-md text-sm text-muted-foreground">
          Organizations let you group repositories and manage team access.
        </p>
      </div>
    )
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card">
      {organizations.data.map((organization, index) => (
        <div
          key={organization.id}
          className={`flex items-center gap-3 px-4 py-3 ${
            index < organizations.data.length - 1 ? "border-b border-border" : ""
          }`}
          data-testid={`organization-${organization.name}`}
        >
          <Building2 className="h-4 w-4 text-muted-foreground" />
          <span className="font-medium text-foreground">{organization.name}</span>
          {organization.description && (
            <span className="truncate text-sm text-muted-foreground">{organization.description}</span>
          )}
        </div>
      ))}
    </div>
  )
}

export function OrganizationsPanel() {
  return (
    <Suspense fallback={<PendingUsers />}>
      <OrganizationsContent />
    </Suspense>
  )
}
