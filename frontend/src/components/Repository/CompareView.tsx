import { useQuery } from "@tanstack/react-query"
import { useNavigate, useParams, useSearch } from "@tanstack/react-router"
import { useState } from "react"
import { repositoriesCompareRevisionsOptions } from "@/client/@tanstack/react-query.gen"
import { Button, Input, Label } from "@/components/design-system"
import { DiffViewer } from "@/components/Repository/DiffViewer"
import RepositoryLoading, { RepositoryError } from "@/components/Repository/RepositoryLoading"

export const CompareView = () => {
  const { owner, repo } = useParams({ from: "/_layout/$owner/$repo/compare" })
  const { base, head } = useSearch({ from: "/_layout/$owner/$repo/compare" })
  const navigate = useNavigate()
  const [baseInput, setBaseInput] = useState(base)
  const [headInput, setHeadInput] = useState(head)
  const { data, isPending, isError, refetch } = useQuery(
    repositoriesCompareRevisionsOptions({ path: { owner, repo }, query: { base, head, include_diff: false } }),
  )
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Compare revisions</h1>
      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={(event) => {
          event.preventDefault()
          navigate({
            to: "/$owner/$repo/compare",
            params: { owner, repo },
            search: { base: baseInput.trim(), head: headInput.trim() },
          })
        }}
      >
        <div className="min-w-48 flex-1">
          <Label htmlFor="compare-base">Base branch, tag, or commit</Label>
          <Input id="compare-base" value={baseInput} onChange={(event) => setBaseInput(event.target.value)} />
        </div>
        <div className="min-w-48 flex-1">
          <Label htmlFor="compare-head">Head branch, tag, or commit</Label>
          <Input id="compare-head" value={headInput} onChange={(event) => setHeadInput(event.target.value)} />
        </div>
        <Button type="submit" size="compact" disabled={!baseInput.trim() || !headInput.trim()}>
          Compare
        </Button>
      </form>
      {isPending ? (
        <RepositoryLoading label="Calculating diff" />
      ) : isError || !data ? (
        <RepositoryError message="Unable to compare revisions." retry={() => refetch()} />
      ) : !data.base_commit || !data.head_commit ? (
        <p className="text-sm text-muted-foreground">One or both revisions could not be found.</p>
      ) : (
        <DiffViewer
          key={`${data.base_commit}/${data.head_commit}`}
          diffSource={{ owner, repo, base: data.base_commit, head: data.head_commit }}
          files={data.files}
          additions={data.additions}
          deletions={data.deletions}
        />
      )}
    </div>
  )
}
