import { useQuery } from "@tanstack/react-query"
import { Check, ChevronDown, Plus } from "lucide-react"
import { useMemo, useState, useSyncExternalStore } from "react"
import { z } from "zod"
import { usersReadUserMeOptions } from "@/client/@tanstack/react-query.gen"
import {
  Button,
  Input,
  Popover,
  PopoverContent,
  PopoverTrigger,
  RepositoryMenuFooter,
  RepositoryMenuHeader,
  RepositoryMenuList,
  StarListOption,
} from "@/components/design-system"
import { isLoggedIn } from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"

const schema = z.array(z.object({ name: z.string(), repos: z.array(z.string()) }))
const initial = JSON.stringify([
  { name: "Favorites", repos: [] },
  { name: "Learning", repos: [] },
])
const subscribe = (notify: () => void) => {
  window.addEventListener("storage", notify)
  window.addEventListener("gitedge:star-lists", notify)
  return () => {
    window.removeEventListener("storage", notify)
    window.removeEventListener("gitedge:star-lists", notify)
  }
}

/** Personal lists stay scoped to the current account in this browser. */
export const StarListMenu = ({
  repository,
  ensureStarred,
  disabled,
}: {
  repository: string
  ensureStarred: () => Promise<unknown>
  disabled: boolean
}) => {
  const { data: user } = useQuery({ ...usersReadUserMeOptions(), enabled: isLoggedIn() })
  const key = `gitedge:star-lists:${user?.id ?? "anonymous"}`
  const serialized = useSyncExternalStore(
    subscribe,
    () => {
      try {
        return localStorage.getItem(key) ?? initial
      } catch {
        return initial
      }
    },
    () => initial,
  )
  const lists = useMemo(() => {
    try {
      return schema.parse(JSON.parse(serialized))
    } catch {
      return schema.parse(JSON.parse(initial))
    }
  }, [serialized])
  const [name, setName] = useState("")
  const [saving, setSaving] = useState(false)
  const { showErrorToast } = useCustomToast()
  const save = async (listName: string, create = false) => {
    if (saving) return
    setSaving(true)
    try {
      const current = lists.find((list) => list.name === listName)
      const removing = !create && current?.repos.includes(repository)
      if (!removing) await ensureStarred()
      const next = current
        ? lists.map((list) =>
            list.name === listName
              ? {
                  ...list,
                  repos: removing
                    ? list.repos.filter((repo) => repo !== repository)
                    : [...new Set([...list.repos, repository])],
                }
              : list,
          )
        : [...lists, { name: listName, repos: [repository] }]
      localStorage.setItem(key, JSON.stringify(next))
      window.dispatchEvent(new Event("gitedge:star-lists"))
      setName("")
    } catch {
      showErrorToast("Unable to save this star list. Please try again.")
    } finally {
      setSaving(false)
    }
  }
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="repository"
          size="icon-sm"
          shape="end"
          aria-label="Add to list"
          disabled={disabled || !user || saving}
        >
          <ChevronDown className="size-3.5" />
        </Button>
      </PopoverTrigger>
      <PopoverContent appearance="starLists" sideOffset={4}>
        <RepositoryMenuHeader muted>Add to list</RepositoryMenuHeader>
        <RepositoryMenuList>
          {lists.map((list) => (
            <StarListOption
              key={list.name}
              selected={list.repos.includes(repository)}
              count={list.repos.length}
              disabled={saving}
              onClick={() => save(list.name)}
            >
              {list.repos.includes(repository) ? (
                <Check className="size-3.5 text-primary" />
              ) : (
                <span className="size-3.5 shrink-0" />
              )}
              {list.name}
            </StarListOption>
          ))}
        </RepositoryMenuList>
        <RepositoryMenuFooter>
          <form
            className="flex items-center gap-1"
            onSubmit={(event) => {
              event.preventDefault()
              if (name.trim()) save(name.trim(), true)
            }}
          >
            <Input
              appearance="starList"
              aria-label="New list name"
              placeholder="New list..."
              value={name}
              maxLength={100}
              onChange={(event) => setName(event.target.value)}
            />
            <Button
              variant="ghost"
              size="icon-xs"
              type="submit"
              aria-label="Create list"
              disabled={!name.trim() || saving}
            >
              <Plus className="size-3.5" />
            </Button>
          </form>
        </RepositoryMenuFooter>
      </PopoverContent>
    </Popover>
  )
}
