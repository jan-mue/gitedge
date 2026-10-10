import { useQuery } from "@tanstack/react-query"

import { watchersListWatchersOptions } from "@/client/@tanstack/react-query.gen"
import PeopleList from "@/components/Repository/PeopleList"

interface WatchersProps {
  owner: string
  repo: string
}

const Watchers = ({ owner, repo }: WatchersProps) => {
  const { data } = useQuery({
    ...watchersListWatchersOptions({ path: { owner, repo } }),
  })

  return <PeopleList users={data?.data ?? []} emptyText="No watchers yet." />
}

export default Watchers
