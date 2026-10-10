import { useQuery } from "@tanstack/react-query"

import { forksListForksOptions } from "@/client/@tanstack/react-query.gen"
import ForksList from "@/components/Repository/ForksList"

interface ForksProps {
  owner: string
  repo: string
}

const Forks = ({ owner, repo }: ForksProps) => {
  const { data } = useQuery({
    ...forksListForksOptions({ path: { owner, repo } }),
  })

  return <ForksList forks={data?.data ?? []} />
}

export default Forks
