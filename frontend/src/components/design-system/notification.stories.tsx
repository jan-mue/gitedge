import type { Meta, StoryObj } from "@storybook/react-vite"
import { Archive, ArrowLeft, CircleDot, Inbox } from "lucide-react"
import { useState } from "react"
import {
  Avatar,
  AvatarFallback,
  Button,
  ChoiceInput,
  NotificationFilter,
  NotificationGroup,
  NotificationItem,
  NotificationReturnNotice,
  NotificationSummary,
  NotificationToolbar,
} from "@/components/design-system"

const meta = {
  title: "Components/Notification center",
  component: NotificationItem,
  args: { selection: null, icon: null, event: null, actor: null, timestamp: null },
  parameters: { layout: "padded" },
} satisfies Meta<typeof NotificationItem>
export default meta
type Story = StoryObj<typeof meta>

const RepositoryExample = ({ unread = true, disabled = false }) => {
  const [selected, setSelected] = useState(false)
  const [isUnread, setUnread] = useState(unread)
  return (
    <NotificationGroup
      selection={
        <ChoiceInput
          type="checkbox"
          aria-label="Select repository"
          checked={selected}
          disabled={disabled}
          onChange={(event) => setSelected(event.target.checked)}
        />
      }
      title="octocat/hello-world"
      actions={
        <Button variant="notificationAction" size="notificationAction" disabled={disabled}>
          Manage
        </Button>
      }
    >
      <NotificationItem
        unread={isUnread}
        selection={
          <ChoiceInput
            type="checkbox"
            aria-label="Select notification"
            checked={selected}
            disabled={disabled}
            onChange={(event) => setSelected(event.target.checked)}
          />
        }
        icon={<CircleDot aria-hidden="true" className="size-4 shrink-0 text-success" />}
        event="Review requested"
        actor={
          <Avatar appearance="notification">
            <AvatarFallback appearance="notification">A</AvatarFallback>
          </Avatar>
        }
        timestamp={<time dateTime="2026-11-02T12:00:00Z">5 min ago</time>}
        actions={
          <Button variant="notificationIcon" size="notificationIcon" aria-label="Dismiss" disabled={disabled}>
            <Archive className="size-4" />
          </Button>
        }
      >
        <Button variant="text" size="text" disabled={disabled} onClick={() => setUnread(!isUnread)}>
          <NotificationSummary title="Add keyboard navigation" number={42} unread={isUnread}>
            Requested your review on this pull request
          </NotificationSummary>
        </Button>
      </NotificationItem>
    </NotificationGroup>
  )
}

export const Unread: Story = { render: () => <RepositoryExample /> }
export const Read: Story = { render: () => <RepositoryExample unread={false} /> }
export const Returned: Story = { render: () => <RepositoryExample unread={false} /> }
export const Busy: Story = { render: () => <RepositoryExample disabled /> }
export const Filters: Story = {
  render: () => (
    <>
      <NotificationFilter aria-pressed count={12}>
        <Inbox className="size-4" />
        Inbox
      </NotificationFilter>
      <NotificationFilter count={3}>Mentioned</NotificationFilter>
      <NotificationFilter mobile aria-pressed count={12}>
        Inbox
      </NotificationFilter>
      <NotificationFilter mobile>Archived</NotificationFilter>
    </>
  ),
}
export const Toolbar: Story = {
  render: () => (
    <NotificationToolbar>
      <ChoiceInput type="checkbox" aria-label="Select all" />
      <span>Select all</span>
      <Button variant="notificationAction" size="notificationAction">
        Mark read
      </Button>
      <Button variant="notificationAction" size="notificationAction">
        Dismiss
      </Button>
    </NotificationToolbar>
  ),
}
export const ReturnNotice: Story = {
  render: () => (
    <NotificationReturnNotice
      action={
        <Button variant="text" size="text">
          <ArrowLeft className="size-4" />
          Back to notifications
        </Button>
      }
    >
      <Inbox className="size-4" />
      Opened from your notifications
    </NotificationReturnNotice>
  ),
}
