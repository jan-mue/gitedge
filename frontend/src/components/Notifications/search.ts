import { z } from "zod"

export const notificationSearchSchema = z.object({
  view: z.enum(["inbox", "archived"]).optional().catch(undefined),
  read: z.enum(["all", "unread"]).optional().catch(undefined),
  reason: z.string().max(40).optional().catch(undefined),
  repo: z.string().max(520).optional().catch(undefined),
  query: z.string().max(255).optional().catch(undefined),
  focus: z.uuid().optional().catch(undefined),
  page: z.coerce.number().int().min(0).optional().catch(undefined),
})

export const notificationOriginSchema = z.object({
  from: z.literal("notifications").optional().catch(undefined),
  n: z.uuid().optional().catch(undefined),
  notification_query: z.string().max(3000).optional().catch(undefined),
})

export type NotificationSearch = z.infer<typeof notificationSearchSchema>
