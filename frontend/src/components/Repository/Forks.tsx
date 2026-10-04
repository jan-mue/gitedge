import { useQuery } from "@tanstack/react-query"

import { ForksService } from "@/client"
import ForksList from "@/components/Repository/ForksList"

interface ForksProps {
  owner: string
  repo: string
}

const Forks = ({ owner, repo }: ForksProps) => {
  const repoPath = `${owner}/${repo}.git`

  const { data } = useQuery({
    queryKey: ["forks", repoPath],
    queryFn: async () => (await ForksService.listForks({ path: { path: repoPath } })).data,
  })

  return <ForksList forks={data?.data ?? []} />
}

export default Forks
