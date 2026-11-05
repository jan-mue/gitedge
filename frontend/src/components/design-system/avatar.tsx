import type { ComponentProps } from "react"
import {
  Avatar as PrimitiveAvatar,
  AvatarFallback as PrimitiveAvatarFallback,
  AvatarImage as PrimitiveAvatarImage,
} from "@/components/ui/avatar"
import { component } from "./component"

const StyledAvatar = component(PrimitiveAvatar, { default: "size-10", profile: "size-16", notification: "size-6" })
export const Avatar = (props: ComponentProps<typeof StyledAvatar>) => <StyledAvatar appearance="default" {...props} />
export const AvatarImage = component(PrimitiveAvatarImage, {})
export const AvatarFallback = component(PrimitiveAvatarFallback, { profile: "text-xl", notification: "text-xs" })
