import type { Meta, StoryObj } from "@storybook/react-vite"
import { handleStarsGetStarState, handleUsersReadUserMe, handleWatchersGetWatchState } from "@/client/msw.gen"
import RepoHeader from "@/components/Repository/RepoHeader"
import { notificationPreferenceHandlers } from "@/components/Storybook/notification-fixtures"
import { handlers, repositoryStoryMeta } from "@/components/Storybook/repository-fixtures"
import { storybookSession, storybookUser } from "@/components/Storybook/StoryRouter"
import StarButton from "./StarButton"
import WatchButton from "./WatchButton"

const preferenceHandlers = [handleUsersReadUserMe({ body: storybookUser }), ...notificationPreferenceHandlers()]
const meta = {
  ...repositoryStoryMeta,
  title: "Patterns/Repository/Header",
  beforeEach: storybookSession,
  parameters: { msw: { handlers: [...preferenceHandlers, ...handlers] } },
} satisfies Meta
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
        ...preferenceHandlers,
        ...handlers.filter((_, index) => index !== 1 && index !== 2),
      ],
    },
  },
}

export const WatchControl: Story = { render: () => <WatchButton owner="jan-mue" repo="gitedge" /> }
export const StarControl: Story = { render: () => <StarButton owner="jan-mue" repo="gitedge" /> }
