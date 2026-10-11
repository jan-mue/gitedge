import { useState } from "react"
import type { LanguageStatistic } from "@/client"

const colors: Record<string, string> = {
  Python: "#3572a5",
  JavaScript: "#f1e05a",
  TypeScript: "#3178c6",
  Go: "#00add8",
  CSS: "#563d7c",
  HTML: "#e34c26",
  Rust: "#dea584",
  Ruby: "#701516",
  Shell: "#89e051",
  JSON: "#9b9b9b",
  Markdown: "#083fa1",
  Other: "#8b949e",
}
const languageColor = (name: string) => colors[name] ?? "#8b949e"

const LanguageBar = ({ languages }: { languages: LanguageStatistic[] }) => {
  const [open, setOpen] = useState(false)
  if (!languages.length) return null
  const total = languages.reduce((sum, language) => sum + language.size, 0)
  return (
    <div>
      <div className="flex h-2 overflow-hidden rounded-full">
        {languages.map((language) => (
          <button
            key={language.name}
            type="button"
            aria-label={`${language.name}: ${language.percentage}%`}
            title={`${language.name}: ${language.percentage}%`}
            aria-expanded={open}
            onClick={() => setOpen((value) => !value)}
            className="h-2 min-w-px transition-opacity hover:opacity-70 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
            style={{ width: `${(language.size / total) * 100}%`, backgroundColor: languageColor(language.name) }}
          />
        ))}
      </div>
      {open && (
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-foreground motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-top-1">
          {languages.map((language) => (
            <span key={language.name} className="flex items-center gap-1.5">
              <span className="size-2.5 rounded-full" style={{ backgroundColor: languageColor(language.name) }} />
              <span className="font-medium">{language.name}</span>
              <span className="text-muted-foreground">{language.percentage}%</span>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
export default LanguageBar
