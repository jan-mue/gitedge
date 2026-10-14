import { GitFork } from "lucide-react"
import { cn } from "@/lib/utils"
import { Link } from "./link"

interface LogoProps {
  variant?: "full" | "icon" | "responsive"
  size?: "default" | "hero" | "compact"
  asLink?: boolean
}
const LogoMark = ({ size, label }: { size: "compact" | "small" | "default" | "hero"; label?: string }) => (
  <span
    className={cn(
      "flex shrink-0 items-center justify-center rounded bg-primary",
      size === "hero" ? "size-20" : size === "default" ? "size-8" : "size-7",
    )}
  >
    <GitFork
      aria-label={label}
      aria-hidden={!label || undefined}
      className={cn(
        "text-primary-foreground",
        size === "hero" ? "size-16" : size === "default" ? "size-6" : size === "compact" ? "size-4" : "size-5",
      )}
    />
  </span>
)
export const Logo = ({ variant = "full", size = "default", asLink = true }: LogoProps) => {
  const content =
    variant === "responsive" ? (
      <>
        <div className="flex items-center gap-2 group-data-[collapsible=icon]:hidden">
          <LogoMark size="default" />
          <span className="text-lg font-bold">GitEdge</span>
        </div>
        <span className="hidden group-data-[collapsible=icon]:block">
          <LogoMark size="small" label="GitEdge" />
        </span>
      </>
    ) : variant === "full" ? (
      <div className={cn("flex items-center gap-2", size === "hero" && "h-16")}>
        <LogoMark size={size === "compact" ? "compact" : "default"} />
        <span className={cn("font-bold", size === "compact" ? "text-sm" : "text-lg")}>GitEdge</span>
      </div>
    ) : (
      <LogoMark label="GitEdge" size={size === "hero" ? "hero" : "small"} />
    )
  return asLink ? (
    <Link to="/" appearance="inherited">
      {content}
    </Link>
  ) : (
    content
  )
}
