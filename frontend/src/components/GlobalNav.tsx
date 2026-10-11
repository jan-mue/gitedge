import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { ChevronDown, GitFork, Inbox, LogOut, Plus, Settings, ShieldCheck, User } from "lucide-react"
import { useState } from "react"
import {
  organizationsCreateOrganizationMutation,
  organizationsListOrganizationsOptions,
  organizationsListOrganizationsQueryKey,
  repositoriesCreateRepositoryMutation,
  repositoriesListRepositoriesQueryKey,
} from "@/client/@tanstack/react-query.gen"
import {
  Button,
  ChoiceInput,
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  Input,
  Label,
  NativeSelect,
  Link as RouterLink,
  Textarea,
} from "@/design-system"
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
          <RouterLink to="/" appearance="brand">
            <div className="flex h-7 w-7 items-center justify-center rounded bg-primary">
              <GitFork className="h-4 w-4 text-primary-foreground" />
            </div>
            <span className="text-sm font-bold">GitEdge</span>
          </RouterLink>

          <div className="flex items-center gap-3">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  type="button"
                  data-testid="create-menu"
                  aria-label="Create repository or organization"
                  variant="outline"
                  size="sm"
                >
                  <Plus className="h-3.5 w-3.5" />
                  <ChevronDown className="h-3 w-3 text-muted-foreground" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" appearance="create">
                <DropdownMenuItem onClick={() => setShowNewRepo(true)}>New Repository</DropdownMenuItem>
                <DropdownMenuItem onClick={() => setShowNewOrg(true)}>New Organization</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            <Button type="button" variant="ghost" size="sm" title="Notifications">
              <Inbox className="h-5 w-5" />
              <span className="absolute -right-0.5 -top-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-primary text-[9px] font-bold text-primary-foreground">
                0
              </span>
            </Button>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  type="button"
                  data-testid="user-menu"
                  aria-label="Open user menu"
                  variant="default"
                  size="icon-sm"
                >
                  {(user?.display_name || username || "U").slice(0, 1).toUpperCase()}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" appearance="account">
                <div className="px-3 py-2 text-sm">
                  <p className="font-medium text-foreground">{user?.display_name || username}</p>
                  <p className="text-xs text-muted-foreground">{user?.email}</p>
                </div>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  <RouterLink to="/profile/$username" params={{ username }} appearance="inherited">
                    <User className="h-4 w-4" />
                    Profile
                  </RouterLink>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <RouterLink to="/settings" appearance="inherited">
                    <Settings className="h-4 w-4" />
                    Settings
                  </RouterLink>
                </DropdownMenuItem>
                {user?.is_superuser && (
                  <>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem asChild>
                      <RouterLink to="/admin" appearance="inherited">
                        <ShieldCheck className="h-4 w-4" />
                        Site Administration
                      </RouterLink>
                    </DropdownMenuItem>
                  </>
                )}
                <DropdownMenuSeparator />
                <DropdownMenuItem appearance="destructive" onClick={logout}>
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
              <Label htmlFor="new-repo-owner" appearance="field">
                Owner
              </Label>
              <NativeSelect
                id="new-repo-owner"
                data-testid="new-repo-owner"
                value={selectedOwner}
                onChange={(e) => setRepoOwner(e.target.value)}
              >
                {ownerOptions.map((owner) => (
                  <option key={owner} value={owner}>
                    {owner}
                  </option>
                ))}
              </NativeSelect>
            </div>
            <div>
              <Label htmlFor="new-repo-name" appearance="field">
                Repository name *
              </Label>
              <Input
                id="new-repo-name"
                data-testid="new-repo-name"
                value={repoName}
                onChange={(e) => setRepoName(e.target.value)}
                placeholder="my-awesome-project"
              />
            </div>
            <div>
              <Label htmlFor="new-repo-desc" appearance="field">
                Description
              </Label>
              <Textarea
                id="new-repo-desc"
                value={repoDesc}
                onChange={(e) => setRepoDesc(e.target.value)}
                placeholder="Short description (optional)"
              />
            </div>
            <div className="flex items-center gap-4">
              <Label appearance="inline">
                <ChoiceInput type="radio" name="visibility" defaultChecked /> Public
              </Label>
              <Label appearance="inline">
                <ChoiceInput type="radio" name="visibility" /> Private
              </Label>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" onClick={() => setShowNewRepo(false)} variant="outline" size="sm">
              Cancel
            </Button>
            <Button
              type="button"
              data-testid="new-repo-submit"
              disabled={!repoName.trim() || createRepoMutation.isPending}
              onClick={() => createRepoMutation.mutate({ body: { owner: selectedOwner, name: repoName.trim() } })}
              variant="success"
              size="sm"
            >
              Create Repository
            </Button>
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
              <Label htmlFor="new-org-name" appearance="field">
                Organization name *
              </Label>
              <Input
                id="new-org-name"
                data-testid="new-org-name"
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                placeholder="my-org"
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" onClick={() => setShowNewOrg(false)} variant="outline" size="sm">
              Cancel
            </Button>
            <Button
              type="button"
              data-testid="new-org-submit"
              disabled={!orgName.trim() || createOrgMutation.isPending}
              onClick={() => createOrgMutation.mutate({ body: { name: orgName.trim() } })}
              variant="success"
              size="sm"
            >
              Create Organization
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

export default GlobalNav
