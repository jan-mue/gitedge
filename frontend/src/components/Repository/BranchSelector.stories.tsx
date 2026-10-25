import type { Meta, StoryObj } from "@storybook/react-vite"
import { type ComponentProps, useState } from "react"
import { type BranchChoice, BranchSelector } from "./BranchSelector"

const choices = [
  { name: "main", is_default: true },
  { name: "develop" },
  { name: "feature/repository-navigation" },
  { name: "archived", disabled: true },
] satisfies BranchChoice[]
const InteractiveBranch = (args: ComponentProps<typeof BranchSelector>) => {
  const [value, setValue] = useState(args.value)
  const [kind, setKind] = useState(args.kind)
  return (
    <BranchSelector
      {...args}
      value={value}
      kind={kind}
      onValueChange={(name, nextKind) => {
        setValue(name)
        setKind(nextKind)
      }}
    />
  )
}
const RetryBranches = ({ tags = false }: { tags?: boolean }) => {
  const [error, setError] = useState(true)
  const [value, setValue] = useState("main")
  const state = tags
    ? { kind: "tag" as const, error: false, tagsError: error }
    : { kind: "branch" as const, error, tagsError: false }
  const branchChoices = state.error ? [] : choices
  const tagChoices = error ? [] : [{ name: "v1.0.0" }]
  return (
    <BranchSelector
      branches={branchChoices}
      tags={tagChoices}
      kind={state.kind}
      value={value}
      onValueChange={setValue}
      status={{
        branch: { error: state.error, onRetry: () => setError(false) },
        tag: { error: state.tagsError, onRetry: () => setError(false) },
      }}
      disclosure={{ defaultOpen: true }}
    />
  )
}
const meta = {
  title: "Components/Branch selector",
  component: BranchSelector,
  args: { branches: choices, tags: [{ name: "v1.0.0" }, { name: "v0.9.0" }], value: "main", onValueChange: () => {} },
  argTypes: {
    branches: {
      control: false,
      table: { type: { summary: "BranchChoice[]" }, defaultValue: { summary: "main, develop, feature, archived" } },
    },
    tags: { control: false },
    onValueChange: { control: false },
    status: { control: false },
  },
  render: (args) => <InteractiveBranch key={args.value} {...args} />,
} satisfies Meta<typeof BranchSelector>
export default meta
type Story = StoryObj<typeof meta>
export const Closed: Story = {}
export const Open: Story = { args: { disclosure: { defaultOpen: true } } }
export const Tags: Story = { args: { kind: "tag", value: "v1.0.0", disclosure: { defaultOpen: true } } }
export const NoTags: Story = { args: { kind: "tag", tags: [], value: "main", disclosure: { defaultOpen: true } } }
export const Disabled: Story = { args: { disabled: true } }
export const Loading: Story = {
  args: { branches: [], status: { branch: { loading: true } }, disclosure: { defaultOpen: true } },
}
export const Empty: Story = { args: { branches: [], value: "", disclosure: { defaultOpen: true } } }
export const LoadError: Story = { render: () => <RetryBranches /> }
export const TagsLoading: Story = {
  args: { kind: "tag", tags: [], status: { tag: { loading: true } }, disclosure: { defaultOpen: true } },
}
export const TagsLoadError: Story = { render: () => <RetryBranches tags /> }
export const LongBranchName: Story = {
  args: {
    branches: [{ name: "feature/a-very-long-branch-name-that-must-fit-the-mobile-viewport" }],
    value: "feature/a-very-long-branch-name-that-must-fit-the-mobile-viewport",
    disclosure: { defaultOpen: true },
  },
}
export const CommitRevision: Story = { args: { value: "28c44f570a4c164912ca71c30bb7c09ba14d0ff4" } }
