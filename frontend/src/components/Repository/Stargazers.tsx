import { useQuery } from "@tanstack/react-query"

import { StarsService } from "@/client"
import PeopleList from "@/components/Repository/PeopleList"

interface StargazersProps {
  owner: string
  repo: string
}

const Stargazers = ({ owner, repo }: StargazersProps) => {
  const repoPath = `${owner}/${repo}.git`

  const { data } = useQuery({
    queryKey: ["stargazers", repoPath],
    queryFn: async () => (await StarsService.listStargazers({ path: { path: repoPath } })).data,
  })

  return <PeopleList users={data?.data ?? []} emptyText="No stargazers yet." />
}

export default Stargazers
