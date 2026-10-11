import type { Meta, StoryObj } from "@storybook/react-vite"
import { CircleCheck, CircleDot, GitMerge, Info } from "lucide-react"
import {
  Alert,
  AlertDescription,
  AlertTitle,
  Avatar,
  AvatarFallback,
  AvatarImage,
  Badge,
  Button,
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
  EmptyState,
  Separator,
  Skeleton,
} from "@/design-system"

const meta = {
  title: "Components/Status and surfaces",
  component: Badge,
  args: { children: "Open", variant: "success" },
} satisfies Meta<typeof Badge>
export default meta
type Story = StoryObj<typeof meta>
export const Badges: Story = {
  render: () => (
    <div className="flex flex-wrap gap-3">
      {(["default", "secondary", "outline", "destructive", "success", "warning", "info", "merged"] as const).map(
        (variant) => (
          <Badge key={variant} variant={variant}>
            {variant}
          </Badge>
        ),
      )}
    </div>
  ),
}
export const RepositoryStates: Story = {
  render: () => (
    <div className="flex flex-wrap gap-3">
      <Badge variant="success">
        <CircleDot aria-hidden="true" />
        Open
      </Badge>
      <Badge variant="secondary">
        <CircleCheck aria-hidden="true" />
        Closed
      </Badge>
      <Badge variant="merged">
        <GitMerge aria-hidden="true" />
        Merged
      </Badge>
      <Badge variant="destructive">Deleted</Badge>
    </div>
  ),
}
export const Information: Story = {
  render: () => (
    <Alert>
      <Info aria-hidden="true" />
      <AlertTitle>Repository visibility</AlertTitle>
      <AlertDescription>This repository is visible to everyone.</AlertDescription>
    </Alert>
  ),
}
export const ErrorAlert: Story = {
  render: () => (
    <Alert variant="destructive">
      <Info aria-hidden="true" />
      <AlertTitle>Unable to save changes</AlertTitle>
      <AlertDescription>Check your connection and try again.</AlertDescription>
    </Alert>
  ),
}
export const Avatars: Story = {
  render: () => (
    <div className="flex items-center gap-4">
      <Avatar>
        <AvatarFallback>JM</AvatarFallback>
      </Avatar>
      <Avatar appearance="profile">
        <AvatarFallback appearance="profile">JM</AvatarFallback>
      </Avatar>
      <Avatar>
        <AvatarImage src="/missing-avatar.png" alt="Jan" />
        <AvatarFallback>J</AvatarFallback>
      </Avatar>
    </div>
  ),
}
export const Empty: Story = {
  render: () => (
    <EmptyState
      title="No repositories yet"
      description="Create a repository or push one to get started"
      actions={<Button>Create repository</Button>}
    />
  ),
}
export const LoadingShapes: Story = {
  render: () => (
    <div className="space-y-5">
      {(
        [
          "short",
          "medium",
          "long",
          "title",
          "email",
          "action",
          "badge",
          "dot",
          "bar",
          "avatar",
          "third",
          "half",
          "trailing",
          "icon",
          "fileTitle",
          "fileMeta",
          "fileSize",
          "fileAction",
          "heading",
          "line",
          "paragraph",
          "codeShort",
          "codeMedium",
          "codeLong",
        ] as const
      ).map((appearance) => (
        <div key={appearance} className="flex items-center gap-4">
          <span className="w-24 shrink-0 text-xs text-muted-foreground">{appearance}</span>
          <Skeleton appearance={appearance} />
        </div>
      ))}
    </div>
  ),
}
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
