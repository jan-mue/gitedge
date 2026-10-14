import type { Meta, StoryObj } from "@storybook/react-vite"
import { Skeleton } from "@/components/design-system"

const meta = { title: "Components/Skeleton" } satisfies Meta
export default meta
type Story = StoryObj

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
