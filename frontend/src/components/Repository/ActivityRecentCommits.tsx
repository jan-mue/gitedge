import type { ActivitySeriesPoint } from "@/client"
import ActivityChart from "@/components/Repository/ActivityChart"

interface ActivityRecentCommitsProps {
  series: ActivitySeriesPoint[]
}

const ActivityRecentCommits = ({ series }: ActivityRecentCommitsProps) => (
  <div className="space-y-4">
    <h2 className="text-lg font-medium text-foreground">Number of commits in the past year</h2>
    <div className="rounded-lg border border-border bg-black/5 p-4 dark:bg-black/20">
      <ActivityChart series={series} height={224} label="Weekly commits in the past year" />
    </div>
  </div>
)

export default ActivityRecentCommits
