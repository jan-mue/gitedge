import type { Meta, StoryObj } from "@storybook/react-vite"
import { GitBranch } from "lucide-react"
import {
  AppShell,
  AuthFooter,
  AuthForm,
  AuthHeading,
  AuthTitle,
  Button,
  EmptyState,
  FieldStack,
  Inline,
  Input,
  Label,
  LanguageBar,
  Logo,
  Page,
  PageHeader,
  Section,
  SectionHeader,
} from "@/design-system"

const meta = { title: "Foundations/Tokens and layout" } satisfies Meta
export default meta
type Story = StoryObj
export const ColorTokens: Story = {
  render: () => (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {[
        ["background", "bg-background text-foreground", "Page canvas"],
        ["card", "bg-card text-card-foreground", "Content surfaces"],
        ["popover", "bg-popover text-popover-foreground", "Menus and dialogs"],
        ["primary", "bg-primary text-primary-foreground", "Primary action"],
        ["secondary", "bg-secondary text-secondary-foreground", "Secondary surface"],
        ["muted", "bg-muted text-muted-foreground", "Supporting content"],
        ["accent", "bg-accent text-accent-foreground", "Hover and selection"],
        ["success", "bg-success-emphasis text-success-foreground", "Open and created"],
        ["destructive", "bg-destructive-emphasis text-destructive-foreground", "Destructive actions"],
        ["warning", "bg-warning text-warning-foreground", "Attention required"],
        ["info", "bg-info-emphasis text-info-foreground", "Information"],
        ["merged", "bg-merged text-merged-foreground", "Merged pull requests"],
        ["sidebar", "bg-sidebar text-sidebar-foreground", "Navigation surface"],
      ].map(([token, classes, usage]) => (
        <div key={token} className={`rounded-lg border border-border p-5 ${classes}`}>
          <p className="font-mono text-sm font-semibold">{token}</p>
          <p className="mt-1 text-sm">{usage}</p>
        </div>
      ))}
    </div>
  ),
}
export const Typography: Story = {
  render: () => (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">Repository heading · Inter</h1>
      <h2 className="text-lg font-semibold">Section heading</h2>
      <p className="text-sm">Body text for repository descriptions, issue titles, and navigation.</p>
      <p className="text-xs text-muted-foreground">Metadata · last updated 2 hours ago</p>
      <code className="font-mono text-sm">git clone https://gitedge-app.vercel.app/jan/gitedge.git</code>
    </div>
  ),
}
export const PageLayout: Story = {
  render: () => (
    <AppShell>
      <Page>
        <PageHeader
          title="Repositories"
          description="View and manage your Git repositories"
          actions={<Button>Create repository</Button>}
        />
        <SectionHeader title="Your repositories" description="Projects you own or contribute to" />
        <Section title="Getting started" icon={GitBranch}>
          <EmptyState
            title="No repositories yet"
            description="Create a repository or push one to get started"
            icon={GitBranch}
          />
        </Section>
      </Page>
    </AppShell>
  ),
}
export const AuthenticationLayout: Story = {
  render: () => (
    <div className="mx-auto max-w-xs">
      <AuthForm onSubmit={(event) => event.preventDefault()}>
        <AuthHeading>
          <AuthTitle>Login to your account</AuthTitle>
        </AuthHeading>
        <FieldStack>
          <Label htmlFor="auth-email">Email</Label>
          <Input id="auth-email" type="email" placeholder="user@example.com" />
          <Inline>
            <Label htmlFor="auth-password">Password</Label>
          </Inline>
          <Input id="auth-password" type="password" placeholder="Password" />
          <Button type="submit" fullWidth>
            Log in
          </Button>
        </FieldStack>
        <AuthFooter>Welcome to GitEdge</AuthFooter>
      </AuthForm>
    </div>
  ),
}
export const LanguageDistribution: Story = {
  render: () => (
    <LanguageBar
      languages={[
        { name: "Python", size: 650, percentage: 65 },
        { name: "TypeScript", size: 300, percentage: 30 },
        { name: "Other", size: 50, percentage: 5 },
      ]}
    />
  ),
}
export const EmptyLanguages: Story = { render: () => <LanguageBar languages={[]} /> }

export const Brand: Story = {
  render: () => (
    <div className="flex items-center gap-6">
      <Logo asLink={false} />
      <Logo variant="icon" asLink={false} />
      <Logo size="hero" asLink={false} />
    </div>
  ),
}
