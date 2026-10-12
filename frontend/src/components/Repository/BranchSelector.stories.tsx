import type { Meta, StoryObj } from "@storybook/react-vite"
import { type ComponentProps, useState } from "react"
import BranchSelector, { type BranchChoice } from "./BranchSelector"

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
  return (
    <BranchSelector
      branches={tags || !error ? choices : []}
      tags={error ? [] : [{ name: "v1.0.0" }]}
      kind={tags ? "tag" : "branch"}
      value={value}
      onValueChange={setValue}
      error={!tags && error}
      tagsError={tags && error}
      onRetryTags={() => setError(false)}
      defaultOpen
      onRetry={() => setError(false)}
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
    onRetry: { control: false },
  },
  render: (args) => <InteractiveBranch key={args.value} {...args} />,
} satisfies Meta<typeof BranchSelector>
export default meta
type Story = StoryObj<typeof meta>
export const Closed: Story = {}
export const Open: Story = { args: { defaultOpen: true } }
export const Tags: Story = { args: { kind: "tag", value: "v1.0.0", defaultOpen: true } }
export const NoTags: Story = { args: { kind: "tag", tags: [], value: "main", defaultOpen: true } }
export const Disabled: Story = { args: { disabled: true } }
export const Loading: Story = { args: { branches: [], loading: true, defaultOpen: true } }
export const Empty: Story = { args: { branches: [], value: "", defaultOpen: true } }
export const LoadError: Story = { render: () => <RetryBranches /> }
export const TagsLoading: Story = { args: { kind: "tag", tags: [], tagsLoading: true, defaultOpen: true } }
export const TagsLoadError: Story = { render: () => <RetryBranches tags /> }
export const LongBranchName: Story = {
  args: {
    branches: [{ name: "feature/a-very-long-branch-name-that-must-fit-the-mobile-viewport" }],
    value: "feature/a-very-long-branch-name-that-must-fit-the-mobile-viewport",
    defaultOpen: true,
  },
}
export const CommitRevision: Story = { args: { value: "28c44f570a4c164912ca71c30bb7c09ba14d0ff4" } }
