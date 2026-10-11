import { useQuery } from "@tanstack/react-query"
import { watchersListWatchersOptions } from "@/client/@tanstack/react-query.gen"
import PeopleList from "@/components/Repository/PeopleList"
import RepositoryLoading, { RepositoryError } from "@/components/Repository/RepositoryLoading"

interface WatchersProps {
  owner: string
  repo: string
}

const Watchers = ({ owner, repo }: WatchersProps) => {
  const { data, isPending, isError, refetch } = useQuery({
    ...watchersListWatchersOptions({ path: { owner, repo } }),
  })

  if (isPending) return <RepositoryLoading label="Loading watchers" />
  if (isError) return <RepositoryError message="Unable to load watchers." retry={() => refetch()} />

  return <PeopleList users={data?.data ?? []} emptyText="No watchers yet." />
}

export default Watchers
