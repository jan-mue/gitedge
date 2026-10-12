import type { ComponentType } from "react"

/** Public components expose named variants; callers cannot override their styles. */
export function component<P extends object, V extends Record<string, string>>(
  Primitive: ComponentType<P>,
  appearances: V,
  base = "",
) {
  return function DesignComponent({ appearance, ...props }: Omit<P, "className" | "style"> & { appearance?: keyof V }) {
    const Comp = Primitive as ComponentType<P & { className: string }>
    return (
      <Comp {...(props as P)} className={[base, appearance && appearances[appearance]].filter(Boolean).join(" ")} />
    )
  }
}
