import { useQuery } from "@tanstack/react-query"

import { ActivityService } from "@/client"
import ActivityList from "@/components/Repository/ActivityList"

interface RepositoryActivityProps {
  owner: string
  repo: string
}

const RepositoryActivity = ({ owner, repo }: RepositoryActivityProps) => {
  const repoPath = `${owner}/${repo}.git`

  const { data } = useQuery({
    queryKey: ["activity", repoPath],
    queryFn: async () => (await ActivityService.getRepositoryActivity({ path: { path: repoPath } })).data,
  })

  return <ActivityList activities={data?.data ?? []} emptyText="No activity in this repository yet." />
}

export default RepositoryActivity
