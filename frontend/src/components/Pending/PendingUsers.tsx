import { Skeleton, TableCell, TableRow } from "@/components/design-system"
import { PendingTable } from "@/components/design-system/table"

const PendingUsers = () => (
  <PendingTable headings={["Full Name", "Email", "Role", "Status"]}>
    {Array.from({ length: 5 }).map((_, index) => (
      <TableRow key={index}>
        <TableCell>
          <Skeleton appearance="medium" />
        </TableCell>
        <TableCell>
          <Skeleton appearance="email" />
        </TableCell>
        <TableCell>
          <Skeleton appearance="badge" />
        </TableCell>
        <TableCell>
          <div className="flex items-center gap-2">
            <Skeleton appearance="dot" />
            <Skeleton appearance="short" />
          </div>
        </TableCell>
        <TableCell>
          <div className="flex justify-end">
            <Skeleton appearance="action" />
          </div>
        </TableCell>
      </TableRow>
    ))}
  </PendingTable>
)

export default PendingUsers
