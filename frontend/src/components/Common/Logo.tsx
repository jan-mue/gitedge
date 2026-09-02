import { Link } from "@tanstack/react-router"
import { GitBranch } from "lucide-react"

import { cn } from "@/lib/utils"

interface LogoProps {
  variant?: "full" | "icon" | "responsive"
  className?: string
  asLink?: boolean
}

export function Logo({
  variant = "full",
  className,
  asLink = true,
}: LogoProps) {
  const content =
    variant === "responsive" ? (
      <>
        <div
          className={cn(
            "flex items-center gap-2 group-data-[collapsible=icon]:hidden",
            className,
          )}
        >
          <GitBranch className="size-6 text-primary" />
          <span className="font-bold text-lg">GitEdge</span>
        </div>
        <GitBranch
          className={cn(
            "size-5 text-primary hidden group-data-[collapsible=icon]:block",
            className,
          )}
        />
      </>
    ) : variant === "full" ? (
      <div className={cn("flex items-center gap-2", className)}>
        <GitBranch className="size-6 text-primary" />
        <span className="font-bold text-lg">GitEdge</span>
      </div>
    ) : (
      <GitBranch className={cn("size-5 text-primary", className)} />
    )

  if (!asLink) {
    return content
  }

  return <Link to="/">{content}</Link>
}
