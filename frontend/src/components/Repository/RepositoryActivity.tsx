import { useQuery } from "@tanstack/react-query"

import { activityGetRepositoryActivityOptions } from "@/client/@tanstack/react-query.gen"
import ActivityList from "@/components/Repository/ActivityList"

interface RepositoryActivityProps {
  owner: string
  repo: string
}

const RepositoryActivity = ({ owner, repo }: RepositoryActivityProps) => {
  const { data } = useQuery({
    ...activityGetRepositoryActivityOptions({ path: { owner, repo } }),
  })

  return <ActivityList activities={data?.data ?? []} emptyText="No activity in this repository yet." />
}

export default RepositoryActivity
