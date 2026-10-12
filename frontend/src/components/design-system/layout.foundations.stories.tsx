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
  Page,
  PageHeader,
  Section,
  SectionHeader,
} from "@/components/design-system"

const meta = { title: "Foundations/Layout" } satisfies Meta
export default meta
type Story = StoryObj

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
