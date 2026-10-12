import {
  Avatar as PrimitiveAvatar,
  AvatarFallback as PrimitiveAvatarFallback,
  AvatarImage as PrimitiveAvatarImage,
} from "@/components/ui/avatar"
import { component } from "./component"
export const Avatar = component(PrimitiveAvatar, { profile: "size-16" }, "size-10")
export const AvatarImage = component(PrimitiveAvatarImage, {})
export const AvatarFallback = component(PrimitiveAvatarFallback, { profile: "text-xl" })
