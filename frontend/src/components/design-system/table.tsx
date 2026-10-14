import type { ComponentProps } from "react"
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

import {
  TableBody as PrimitiveTableBody,
  TableCaption as PrimitiveTableCaption,
  TableCell as PrimitiveTableCell,
  TableFooter as PrimitiveTableFooter,
  TableHead as PrimitiveTableHead,
  TableHeader as PrimitiveTableHeader,
  TableRow as PrimitiveTableRow,
} from "@/components/ui/table"
import { component } from "./component"

export const TableHeader = component(PrimitiveTableHeader, {}, "bg-transparent")
export const TableBody = component(PrimitiveTableBody, {})
export const TableFooter = component(PrimitiveTableFooter, {})
export const TableHead = component(PrimitiveTableHead, {}, "h-12 px-4 text-muted-foreground")
export const TableRow = component(PrimitiveTableRow, { static: "hover:bg-transparent" })
export const TableCell = component(PrimitiveTableCell, { empty: "h-32 text-center text-muted-foreground" }, "p-4")
export const TableCaption = component(PrimitiveTableCaption, {})
