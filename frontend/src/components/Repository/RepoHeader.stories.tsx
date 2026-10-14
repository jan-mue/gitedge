import type { Meta, StoryObj } from "@storybook/react-vite"
import { handleStarsGetStarState, handleWatchersGetWatchState } from "@/client/msw.gen"
import RepoHeader from "@/components/Repository/RepoHeader"
import { handlers, repositoryStoryMeta } from "@/components/Storybook/repository-fixtures"

const meta = { ...repositoryStoryMeta, title: "Patterns/Repository/Header" } satisfies Meta
export default meta
type Story = StoryObj

export const Header: Story = { render: () => <RepoHeader owner="jan-mue" repo="gitedge" /> }
export const SelectedActions: Story = {
  ...Header,
  parameters: {
    msw: {
      handlers: [
        handleStarsGetStarState({ body: { is_starred: true, stars_count: 129 } }),
        handleWatchersGetWatchState({ body: { is_watching: true, watchers_count: 33 } }),
        ...handlers.slice(2),
      ],
    },
  },
}
