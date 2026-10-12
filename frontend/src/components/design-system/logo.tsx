import { GitBranch } from "lucide-react"
import { cn } from "@/lib/utils"
import { Link } from "./link"

interface LogoProps {
  variant?: "full" | "icon" | "responsive"
  size?: "default" | "hero"
  asLink?: boolean
}
export const Logo = ({ variant = "full", size = "default", asLink = true }: LogoProps) => {
  const content =
    variant === "responsive" ? (
      <>
        <div className="flex items-center gap-2 group-data-[collapsible=icon]:hidden">
          <GitBranch className="size-6 text-primary" />
          <span className="text-lg font-bold">GitEdge</span>
        </div>
        <GitBranch className="hidden size-5 text-primary group-data-[collapsible=icon]:block" />
      </>
    ) : variant === "full" ? (
      <div className={cn("flex items-center gap-2", size === "hero" && "h-16")}>
        <GitBranch className="size-6 text-primary" />
        <span className="text-lg font-bold">GitEdge</span>
      </div>
    ) : (
      <GitBranch aria-label="GitEdge" className={cn("size-5 text-primary", size === "hero" && "size-16")} />
    )
  return asLink ? (
    <Link to="/" appearance="inherited">
      {content}
    </Link>
  ) : (
    content
  )
}
