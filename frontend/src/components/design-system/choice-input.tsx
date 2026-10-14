import type { ComponentProps } from "react"
export const ChoiceInput = (props: Omit<ComponentProps<"input">, "className" | "style">) => (
  <input
    {...props}
    className="size-[13px] accent-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:opacity-50"
  />
)
