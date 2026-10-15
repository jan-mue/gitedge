import type { ComponentProps } from "react"
export const ChoiceInput = ({
  appearance,
  ...props
}: Omit<ComponentProps<"input">, "className" | "style"> & { appearance?: "notification" | "notificationSwitch" }) => (
  <input
    {...props}
    className={`${appearance === "notificationSwitch" ? "appearance-none w-11 h-6 rounded-full bg-input checked:bg-primary transition-colors relative before:absolute before:top-0.5 before:left-0.5 before:size-5 before:rounded-full before:bg-background before:shadow before:transition-transform checked:before:translate-x-5" : appearance === "notification" ? "size-4 shrink-0" : "size-[13px]"} accent-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:opacity-50`}
  />
)
