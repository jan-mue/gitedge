import { useQuery } from "@tanstack/react-query"

import { WatchersService } from "@/client"
import PeopleList from "@/components/Repository/PeopleList"

interface WatchersProps {
  owner: string
  repo: string
}

const Watchers = ({ owner, repo }: WatchersProps) => {
  const repoPath = `${owner}/${repo}.git`

  const { data } = useQuery({
    queryKey: ["watchers", repoPath],
    queryFn: async () => (await WatchersService.listWatchers({ path: { path: repoPath } })).data,
  })

  return <PeopleList users={data?.data ?? []} emptyText="No watchers yet." />
}

export default Watchers
