import type { Meta, StoryObj } from "@storybook/react-vite"
import { LogViewer } from "./log-viewer"

const meta = {
  title: "Components/Log viewer",
  component: LogViewer,
  args: {
    sections: [
      {
        id: "checkout",
        name: "Checkout code",
        status: "success",
        log: "Fetching repository\nHEAD is now at b47bca7 Add Actions checks\n",
      },
      { id: "test", name: "Run unit tests", status: "success", log: "bun test\n  12 pass\n   0 fail\n" },
    ],
    log: "Run Checkout code\nFetching repository\nCheckout code: success\nRun unit tests\nbun test\n12 pass\n0 fail\nRun unit tests: success",
  },
} satisfies Meta<typeof LogViewer>
export default meta
type Story = StoryObj<typeof meta>

export const Successful: Story = {}
export const Running: Story = {
  args: {
    sections: [
      {
        id: "test",
        name: "Run integration tests",
        status: "running",
        log: "Collected 23 tests\nStarting database container…",
      },
    ],
  },
}
export const Failed: Story = {
  args: {
    sections: [
      {
        id: "test",
        name: "Run unit tests",
        status: "failure",
        log: "Expected: 200\nReceived: 500\n\n1 failed, 11 passed\nProcess exited with code 1",
      },
    ],
  },
}
export const UntrustedText: Story = {
  args: {
    sections: [
      {
        id: "output",
        name: "Application output",
        status: "failure",
        log: '<script>alert("This remains plain text")</script>\nToken: ***',
      },
    ],
  },
}
export const LongOutput: Story = {
  args: {
    sections: [
      {
        id: "test",
        name: "Long test output",
        status: "running",
        log: Array.from({ length: 200 }, (_, line) => `Test ${line + 1}: passed`).join("\n"),
      },
    ],
  },
}
export const Empty: Story = { args: { sections: [], log: "" } }

export const RecentOutput: Story = {
  args: { truncated: true, sections: [{ id: "test", name: "Tests", status: "running", log: "Latest test output…" }] },
}
