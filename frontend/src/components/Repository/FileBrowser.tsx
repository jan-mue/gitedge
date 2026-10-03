import { useNavigate } from "@tanstack/react-router"
import { Check, FileText, Folder, MoreHorizontal } from "lucide-react"

import type { CommitInfo, TreeEntry } from "@/client"

interface FileBrowserProps {
  entries: TreeEntry[]
  owner: string
  repo: string
  treePath?: string
  searchRef?: string
  lastCommit?: CommitInfo | null
}

const formatRelativeDate = (timestamp: number): string => {
  const now = Date.now() / 1000
  const diff = now - timestamp
  if (diff < 60) return "just now"
  if (diff < 3600) return `${Math.floor(diff / 60)} minutes ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)} hours ago`
  if (diff < 2592000) return `${Math.floor(diff / 86400)} days ago`
  if (diff < 31536000) return `${Math.floor(diff / 2592000)} months ago`
  return `${Math.floor(diff / 31536000)} years ago`
}

const FileBrowser = ({
  entries,
  owner,
  repo,
  treePath,
  searchRef,
  lastCommit,
}: FileBrowserProps) => {
  const navigate = useNavigate()

  const handleEntryClick = (entry: TreeEntry) => {
    if (entry.type === "tree") {
      navigate({
        to: "/$owner/$repo",
        params: { owner, repo },
        search: { ref: searchRef, path: entry.path },
      })
    } else {
      navigate({
        to: "/$owner/$repo/blob",
        params: { owner, repo },
        search: { ref: searchRef, path: entry.path },
      })
    }
  }

  const handleParentClick = () => {
    const parentPath = treePath?.split("/").slice(0, -1).join("/")
    navigate({
      to: "/$owner/$repo",
      params: { owner, repo },
      search: { ref: searchRef, path: parentPath || undefined },
    })
  }

  return (
    <div
      className="border border-border rounded-lg overflow-hidden"
      data-testid="file-tree"
    >
      {/* Last commit bar */}
      {lastCommit && (
        <div className="flex items-center gap-3 px-4 py-2.5 bg-secondary border-b border-border">
          <div className="w-6 h-6 rounded-full bg-accent flex items-center justify-center text-xs font-medium text-accent-foreground">
            {lastCommit.author.charAt(0).toUpperCase()}
          </div>
          <span className="text-sm font-medium text-foreground">
            {lastCommit.author}
          </span>
          <code className="px-1.5 py-0.5 text-xs font-mono bg-accent rounded text-primary">
            {lastCommit.sha.slice(0, 10)}
          </code>
          <Check className="w-4 h-4 text-success" />
          <span className="text-sm text-foreground truncate flex-1">
            {lastCommit.message.split("\n")[0]}
          </span>
          <button
            type="button"
            className="p-1 rounded hover:bg-accent transition-colors"
          >
            <MoreHorizontal className="w-4 h-4 text-muted-foreground" />
          </button>
          <span className="text-sm text-muted-foreground whitespace-nowrap">
            {formatRelativeDate(lastCommit.timestamp)}
          </span>
        </div>
      )}

      {/* Back link for subdirectories */}
      {treePath && (
        <button
          type="button"
          onClick={handleParentClick}
          className="flex items-center gap-3 px-4 py-2 hover:bg-accent/50 border-b border-border text-sm text-primary transition-colors w-full text-left"
          data-testid="tree-entry-parent"
        >
          <Folder className="w-4 h-4 text-primary flex-shrink-0" />
          <span>..</span>
        </button>
      )}

      {/* File list */}
      {entries.map((entry, index) => (
        <button
          key={entry.path}
          type="button"
          onClick={() => handleEntryClick(entry)}
          className={`flex items-center gap-3 px-4 py-2 hover:bg-accent/50 text-sm transition-colors w-full text-left ${
            index < entries.length - 1 || treePath
              ? "border-b border-border"
              : ""
          }`}
          data-testid={`tree-entry-${entry.name}`}
        >
          {entry.type === "tree" ? (
            <Folder className="w-4 h-4 text-primary flex-shrink-0" />
          ) : (
            <FileText className="w-4 h-4 text-muted-foreground flex-shrink-0" />
          )}
          <span
            className={
              entry.type === "tree"
                ? "text-primary font-medium"
                : "text-foreground"
            }
          >
            {entry.name}
          </span>
        </button>
      ))}

      {entries.length === 0 && !treePath && (
        <div className="text-center text-muted-foreground py-8 text-sm">
          This repository is empty
        </div>
      )}
    </div>
  )
}

export default FileBrowser
