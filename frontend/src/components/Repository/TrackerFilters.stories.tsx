import type { Meta, StoryObj } from "@storybook/react-vite"
import { Button } from "@/components/design-system"
import TrackerFilters, { TrackerSearch, useTrackerFilters } from "./TrackerFilters"
import { trackerPulls } from "./tracker-story-fixtures"

const FiltersPreview = () => {
  const filters = useTrackerFilters(trackerPulls)
  return (
    <div className="space-y-4">
      <TrackerSearch filters={filters} label="pull requests">
        <Button variant="success" size="compact">
          New pull request
        </Button>
      </TrackerSearch>
      <div className="overflow-hidden rounded-lg border border-border">
        <TrackerFilters filters={filters} kind="pulls" openCount={2} closedCount={1} mergedCount={1} totalCount={3} />
        <div className="p-4 text-sm text-muted-foreground" aria-live="polite">
          {filters.filtered.length} matching pull requests
        </div>
      </div>
    </div>
  )
}
const meta = { title: "Patterns/Repository/Tracker filters", component: TrackerFilters } satisfies Meta<
  typeof TrackerFilters
>
export default meta
type Story = StoryObj
export const Interactive: Story = { render: () => <FiltersPreview /> }
