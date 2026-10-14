import { Skeleton, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/design-system"

const PendingUsers = () => (
  <Table>
    <TableHeader>
      <TableRow>
        <TableHead>Full Name</TableHead>
        <TableHead>Email</TableHead>
        <TableHead>Role</TableHead>
        <TableHead>Status</TableHead>
        <TableHead>
          <span className="sr-only">Actions</span>
        </TableHead>
      </TableRow>
    </TableHeader>
    <TableBody>
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
    </TableBody>
  </Table>
)

export default PendingUsers
