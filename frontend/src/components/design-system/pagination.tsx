import {
  Pagination as PrimitivePagination,
  PaginationContent as PrimitivePaginationContent,
  PaginationEllipsis as PrimitivePaginationEllipsis,
  PaginationItem as PrimitivePaginationItem,
  PaginationLink as PrimitivePaginationLink,
  PaginationNext as PrimitivePaginationNext,
  PaginationPrevious as PrimitivePaginationPrevious,
} from "@/components/ui/pagination"
import { component } from "./component"
export const Pagination = component(PrimitivePagination, {})
export const PaginationContent = component(PrimitivePaginationContent, {})
export const PaginationLink = component(PrimitivePaginationLink, {})
export const PaginationItem = component(PrimitivePaginationItem, {})
export const PaginationPrevious = component(PrimitivePaginationPrevious, {})
export const PaginationNext = component(PrimitivePaginationNext, {})
export const PaginationEllipsis = component(PrimitivePaginationEllipsis, {})
