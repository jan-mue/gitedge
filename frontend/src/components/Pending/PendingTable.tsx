import type { ReactNode } from "react"
import { Table, TableBody, TableHead, TableHeader, TableRow } from "@/components/design-system"

export const PendingTable = ({ headings, children }: { headings: string[]; children: ReactNode }) => {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          {headings.map((heading) => (
            <TableHead key={heading}>{heading}</TableHead>
          ))}
          <TableHead>
            <span className="sr-only">Actions</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>{children}</TableBody>
    </Table>
  )
}
