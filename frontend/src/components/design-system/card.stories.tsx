import type { Meta, StoryObj } from "@storybook/react-vite"
import {
  Badge,
  Button,
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
  Separator,
} from "@/components/design-system"

const meta = { title: "Components/Card" } satisfies Meta
export default meta
type Story = StoryObj

export const RepositoryCard: Story = {
  render: () => (
    <Card>
      <CardHeader>
        <CardTitle>jan-mue / gitedge</CardTitle>
        <CardDescription>Git hosting at the edge</CardDescription>
        <CardAction>
          <Badge variant="outline">Public</Badge>
        </CardAction>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">
          Git objects in blob storage, refs in Redis, metadata in PostgreSQL.
        </p>
        <Separator />
      </CardContent>
      <CardFooter>
        <Button variant="outline">View repository</Button>
      </CardFooter>
    </Card>
  ),
}
