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

export const TableHeader = component(PrimitiveTableHeader, { access: "bg-secondary" }, "bg-transparent")
export const TableBody = component(PrimitiveTableBody, {})
export const TableFooter = component(PrimitiveTableFooter, {})
export const TableHead = component(
  PrimitiveTableHead,
  { access: "px-5 text-base font-normal normal-case tracking-normal text-foreground" },
  "h-12 px-4 text-muted-foreground",
)
export const TableRow = component(PrimitiveTableRow, { static: "hover:bg-transparent" })
export const TableCell = component(
  PrimitiveTableCell,
  {
    empty: "h-32 text-center text-muted-foreground",
    access: "h-24 px-5 py-4",
    selection: "w-14 pl-5 pr-0",
    action: "w-16 pl-0 pr-5",
  },
  "p-4",
)
export const TableCaption = component(PrimitiveTableCaption, {})
