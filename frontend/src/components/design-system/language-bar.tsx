import { useState } from "react"

type LanguageStatistic = { name: string; size: number; percentage: number }

const languages = new Set([
  "python",
  "javascript",
  "typescript",
  "go",
  "css",
  "html",
  "rust",
  "ruby",
  "shell",
  "json",
  "markdown",
])
const languageColor = (name: string) =>
  `var(--language-${languages.has(name.toLowerCase()) ? name.toLowerCase() : "other"})`

const LanguageBar = ({ languages }: { languages: LanguageStatistic[] }) => {
  const [open, setOpen] = useState(false)
  if (!languages.length) return null
  const total = languages.reduce((sum, language) => sum + language.size, 0)
  if (total <= 0) return null
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
