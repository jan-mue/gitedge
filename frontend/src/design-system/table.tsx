import type { ComponentProps } from "react"
/** Keyboard users can reach horizontal content without relying on a pointer. */
export const Table = ({
  scrollLabel = "Data table",
  ...props
}: Omit<ComponentProps<"table">, "className" | "style"> & { scrollLabel?: string }) => (
  <section
    data-slot="table-container"
    aria-label={scrollLabel}
    // biome-ignore lint/a11y/noNoninteractiveTabindex: scroll regions must be reachable for keyboard scrolling
    tabIndex={0}
    className="relative w-full overflow-x-auto rounded-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
  >
    <table {...props} data-slot="table" className="w-full caption-bottom text-sm" />
  </section>
)
