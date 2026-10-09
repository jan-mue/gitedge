import type { UserPublic } from "@/client"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"

interface PeopleListProps {
  users: UserPublic[]
  emptyText: string
}

const initials = (user: UserPublic) => {
  const source = user.display_name || user.name || user.email
  return source.slice(0, 1).toUpperCase()
}

const PeopleList = ({ users, emptyText }: PeopleListProps) => {
  if (users.length === 0) {
    return <div className="py-12 text-center text-sm text-muted-foreground">{emptyText}</div>
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" data-testid="people-list">
      {users.map((user) => (
        <div key={user.id} className="flex items-center gap-3 border border-border rounded-lg bg-card px-4 py-3">
          <Avatar>
            <AvatarFallback>{initials(user)}</AvatarFallback>
          </Avatar>
          <div className="min-w-0">
            <p className="text-sm font-medium text-foreground truncate">{user.display_name || user.name}</p>
            <p className="text-xs text-muted-foreground truncate">{user.name ?? user.email}</p>
          </div>
        </div>
      ))}
    </div>
  )
}

export default PeopleList
