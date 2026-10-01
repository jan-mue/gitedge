import { GitBranch } from "lucide-react"

interface RefBadgeProps {
  gitRef: string
  "data-testid"?: string
}

const RefBadge = ({ gitRef, ...props }: RefBadgeProps) => (
  <div className="flex items-center gap-2 text-sm text-muted-foreground">
    <GitBranch className="h-4 w-4" />
    <span data-testid={props["data-testid"]}>{gitRef}</span>
  </div>
)

export default RefBadge
