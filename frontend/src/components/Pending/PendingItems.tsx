import { Skeleton, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/design-system"

const PendingItems = () => (
  <Table>
    <TableHeader>
      <TableRow>
        <TableHead>ID</TableHead>
        <TableHead>Title</TableHead>
        <TableHead>Description</TableHead>
        <TableHead>
          <span className="sr-only">Actions</span>
        </TableHead>
      </TableRow>
    </TableHeader>
    <TableBody>
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
    </TableBody>
  </Table>
)

export default PendingItems
