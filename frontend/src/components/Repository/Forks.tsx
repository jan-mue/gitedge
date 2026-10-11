import { useQuery } from "@tanstack/react-query"
import { forksListForksOptions } from "@/client/@tanstack/react-query.gen"
import ForksList from "@/components/Repository/ForksList"
import RepositoryLoading, { RepositoryError } from "@/components/Repository/RepositoryLoading"

interface ForksProps {
  owner: string
  repo: string
}

const Forks = ({ owner, repo }: ForksProps) => {
  const { data, isPending, isError, refetch } = useQuery({
    ...forksListForksOptions({ path: { owner, repo } }),
  })

  if (isPending) return <RepositoryLoading label="Loading forks" />
  if (isError) return <RepositoryError message="Unable to load forks." retry={() => refetch()} />

  return <ForksList forks={data?.data ?? []} />
}

export default Forks
