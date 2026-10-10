import { useQuery } from "@tanstack/react-query"

import { starsListStargazersOptions } from "@/client/@tanstack/react-query.gen"
import PeopleList from "@/components/Repository/PeopleList"

interface StargazersProps {
  owner: string
  repo: string
}

const Stargazers = ({ owner, repo }: StargazersProps) => {
  const { data } = useQuery({
    ...starsListStargazersOptions({ path: { owner, repo } }),
  })

  return <PeopleList users={data?.data ?? []} emptyText="No stargazers yet." />
}

export default Stargazers
