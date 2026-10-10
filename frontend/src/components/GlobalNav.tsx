import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link as RouterLink, useNavigate } from "@tanstack/react-router"
import { ChevronDown, GitFork, Inbox, LogOut, Plus, Settings, ShieldCheck, User } from "lucide-react"
import { useState } from "react"

import {
  organizationsCreateOrganizationMutation,
  organizationsListOrganizationsOptions,
  organizationsListOrganizationsQueryKey,
  repositoriesCreateRepositoryMutation,
  repositoriesListRepositoriesQueryKey,
} from "@/client/@tanstack/react-query.gen"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const GlobalNav = () => {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user, logout } = useAuth()
  const { showErrorToast } = useCustomToast()

  const [showNewRepo, setShowNewRepo] = useState(false)
  const [showNewOrg, setShowNewOrg] = useState(false)
  const [repoName, setRepoName] = useState("")
  const [repoDesc, setRepoDesc] = useState("")
  const [repoOwner, setRepoOwner] = useState("")
  const [orgName, setOrgName] = useState("")

  const username = user?.name ?? ""

  const { data: organizations } = useQuery({
    ...organizationsListOrganizationsOptions(),
  })

  const ownerOptions = [username, ...(organizations?.data.map((org) => org.name) ?? [])].filter(Boolean)
  const selectedOwner = repoOwner || username

  const createRepoMutation = useMutation({
    ...repositoriesCreateRepositoryMutation(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: repositoriesListRepositoriesQueryKey() })
      setShowNewRepo(false)
      setRepoName("")
      setRepoDesc("")
      navigate({ to: "/$owner/$repo", params: { owner: selectedOwner, repo: repoName.trim() } })
    },
    onError: handleError.bind(showErrorToast),
  })

  const createOrgMutation = useMutation({
    ...organizationsCreateOrganizationMutation(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: organizationsListOrganizationsQueryKey() })
      setShowNewOrg(false)
      setOrgName("")
    },
    onError: handleError.bind(showErrorToast),
  })

  return (
    <>
      <nav className="border-b border-border bg-secondary">
        <div className="container mx-auto flex h-12 max-w-7xl items-center justify-between gap-2 px-4">
          <RouterLink to="/" className="flex items-center gap-2 text-foreground transition-colors hover:text-primary">
            <div className="flex h-7 w-7 items-center justify-center rounded bg-primary">
              <GitFork className="h-4 w-4 text-primary-foreground" />
            </div>
            <span className="text-sm font-bold">GitEdge</span>
          </RouterLink>

          <div className="flex items-center gap-3">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  data-testid="create-menu"
                  className="flex items-center gap-1 rounded border border-border bg-background px-2 py-1 text-sm text-foreground transition-colors hover:bg-accent"
                >
                  <Plus className="h-3.5 w-3.5" />
                  <ChevronDown className="h-3 w-3 text-muted-foreground" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-48">
                <DropdownMenuItem onClick={() => setShowNewRepo(true)}>New Repository</DropdownMenuItem>
                <DropdownMenuItem onClick={() => setShowNewOrg(true)}>New Organization</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            <button
              type="button"
              className="relative rounded p-1.5 text-foreground transition-colors hover:bg-accent"
              title="Notifications"
            >
              <Inbox className="h-5 w-5" />
              <span className="absolute -right-0.5 -top-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-primary text-[9px] font-bold text-primary-foreground">
                0
              </span>
            </button>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  data-testid="user-menu"
                  className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
                >
                  {(user?.display_name || username || "U").slice(0, 1).toUpperCase()}
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-52">
                <div className="px-3 py-2 text-sm">
                  <p className="font-medium text-foreground">{user?.display_name || username}</p>
                  <p className="text-xs text-muted-foreground">{user?.email}</p>
                </div>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  <RouterLink
                    to="/profile/$username"
                    params={{ username }}
                    className="flex cursor-pointer items-center gap-2"
                  >
                    <User className="h-4 w-4" />
                    Profile
                  </RouterLink>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <RouterLink to="/settings" className="flex cursor-pointer items-center gap-2">
                    <Settings className="h-4 w-4" />
                    Settings
                  </RouterLink>
                </DropdownMenuItem>
                {user?.is_superuser && (
                  <>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem asChild>
                      <RouterLink to="/admin" className="flex cursor-pointer items-center gap-2">
                        <ShieldCheck className="h-4 w-4" />
                        Site Administration
                      </RouterLink>
                    </DropdownMenuItem>
                  </>
                )}
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  className="flex cursor-pointer items-center gap-2 text-destructive focus:text-destructive"
                  onClick={logout}
                >
                  <LogOut className="h-4 w-4" />
                  Sign Out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </nav>

      <Dialog open={showNewRepo} onOpenChange={setShowNewRepo}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New Repository</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <label htmlFor="new-repo-owner" className="mb-1 block text-sm font-medium text-foreground">
                Owner
              </label>
              <select
                id="new-repo-owner"
                data-testid="new-repo-owner"
                value={selectedOwner}
                onChange={(e) => setRepoOwner(e.target.value)}
                className="w-full rounded border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              >
                {ownerOptions.map((owner) => (
                  <option key={owner} value={owner}>
                    {owner}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="new-repo-name" className="mb-1 block text-sm font-medium text-foreground">
                Repository name *
              </label>
              <input
                id="new-repo-name"
                data-testid="new-repo-name"
                value={repoName}
                onChange={(e) => setRepoName(e.target.value)}
                className="w-full rounded border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="my-awesome-project"
              />
            </div>
            <div>
              <label htmlFor="new-repo-desc" className="mb-1 block text-sm font-medium text-foreground">
                Description
              </label>
              <textarea
                id="new-repo-desc"
                value={repoDesc}
                onChange={(e) => setRepoDesc(e.target.value)}
                className="h-20 w-full resize-none rounded border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="Short description (optional)"
              />
            </div>
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 text-sm text-foreground">
                <input type="radio" name="visibility" defaultChecked className="accent-primary" /> Public
              </label>
              <label className="flex items-center gap-2 text-sm text-foreground">
                <input type="radio" name="visibility" className="accent-primary" /> Private
              </label>
            </div>
          </div>
          <DialogFooter>
            <button
              type="button"
              onClick={() => setShowNewRepo(false)}
              className="rounded border border-border bg-secondary px-4 py-2 text-sm text-foreground hover:bg-accent"
            >
              Cancel
            </button>
            <button
              type="button"
              data-testid="new-repo-submit"
              disabled={!repoName.trim() || createRepoMutation.isPending}
              onClick={() => createRepoMutation.mutate({ body: { owner: selectedOwner, name: repoName.trim() } })}
              className="rounded bg-success px-4 py-2 text-sm font-medium text-success-foreground hover:opacity-90 disabled:opacity-50"
            >
              Create Repository
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={showNewOrg} onOpenChange={setShowNewOrg}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New Organization</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <label htmlFor="new-org-name" className="mb-1 block text-sm font-medium text-foreground">
                Organization name *
              </label>
              <input
                id="new-org-name"
                data-testid="new-org-name"
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                className="w-full rounded border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="my-org"
              />
            </div>
          </div>
          <DialogFooter>
            <button
              type="button"
              onClick={() => setShowNewOrg(false)}
              className="rounded border border-border bg-secondary px-4 py-2 text-sm text-foreground hover:bg-accent"
            >
              Cancel
            </button>
            <button
              type="button"
              data-testid="new-org-submit"
              disabled={!orgName.trim() || createOrgMutation.isPending}
              onClick={() => createOrgMutation.mutate({ body: { name: orgName.trim() } })}
              className="rounded bg-success px-4 py-2 text-sm font-medium text-success-foreground hover:opacity-90 disabled:opacity-50"
            >
              Create Organization
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

export default GlobalNav
