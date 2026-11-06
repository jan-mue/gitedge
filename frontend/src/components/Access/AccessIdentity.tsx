import { Users } from "lucide-react"
import { Avatar, AvatarFallback, Link } from "@/components/design-system"

export interface AccessPerson {
  id: string
  name: string
  displayName?: string | null
  kind: "user" | "team"
}

export const AccessIdentity = ({
  person,
  detail,
  linked = false,
}: {
  person: AccessPerson
  detail: string
  linked?: boolean
}) => (
  <div className="flex min-w-0 items-center gap-4">
    <Avatar>
      <AvatarFallback>
        {person.kind === "team" ? (
          <Users className="size-5" aria-hidden="true" />
        ) : (
          (person.displayName || person.name).slice(0, 2).toUpperCase()
        )}
      </AvatarFallback>
    </Avatar>
    <div className="min-w-0 space-y-1">
      <div className="truncate text-base font-semibold">
        {linked && person.kind === "user" ? (
          <Link to="/profile/$username" params={{ username: person.name }} appearance="strong">
            {person.displayName || person.name}
          </Link>
        ) : (
          person.displayName || person.name
        )}
      </div>
      <p className="truncate text-sm text-muted-foreground">
        {person.displayName ? `${person.name} · ` : ""}
        {detail}
      </p>
    </div>
  </div>
)
