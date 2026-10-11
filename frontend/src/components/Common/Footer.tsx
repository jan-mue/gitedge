import { FaGithub } from "react-icons/fa"
import { ExternalLink } from "@/design-system"

const socialLinks = [
  {
    icon: FaGithub,
    href: "https://github.com/jan-mue/gitedge",
    label: "GitHub",
  },
]

export function Footer() {
  const currentYear = new Date().getFullYear()

  return (
    <footer className="border-t py-4 px-6">
      <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
        <p className="text-muted-foreground text-sm">GitEdge - {currentYear}</p>
        <div className="flex items-center gap-4">
          {socialLinks.map(({ icon: Icon, href, label }) => (
            <ExternalLink
              key={label}
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={label}
              appearance="social"
            >
              <Icon className="h-5 w-5" />
            </ExternalLink>
          ))}
        </div>
      </div>
    </footer>
  )
}
