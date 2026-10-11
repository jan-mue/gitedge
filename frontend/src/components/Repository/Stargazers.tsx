import { useQuery } from "@tanstack/react-query"
import { starsListStargazersOptions } from "@/client/@tanstack/react-query.gen"
import PeopleList from "@/components/Repository/PeopleList"
import RepositoryLoading, { RepositoryError } from "@/components/Repository/RepositoryLoading"

interface StargazersProps {
  owner: string
  repo: string
}

const Stargazers = ({ owner, repo }: StargazersProps) => {
  const { data, isPending, isError, refetch } = useQuery({
    ...starsListStargazersOptions({ path: { owner, repo } }),
  })

  if (isPending) return <RepositoryLoading label="Loading stargazers" />
  if (isError) return <RepositoryError message="Unable to load stargazers." retry={() => refetch()} />

  return <PeopleList users={data?.data ?? []} emptyText="No stargazers yet." />
}

export default Stargazers
