import { Skeleton, TableCell, TableRow } from "@/components/design-system"
import { PendingTable } from "@/components/design-system/table"

const PendingItems = () => (
  <PendingTable headings={["ID", "Title", "Description"]}>
    {Array.from({ length: 5 }).map((_, index) => (
      <TableRow key={index}>
        <TableCell>
          <Skeleton appearance="title" />
        </TableCell>
        <TableCell>
          <Skeleton appearance="medium" />
        </TableCell>
        <TableCell>
          <Skeleton appearance="long" />
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

export default PendingItems
