import {
  Alert as PrimitiveAlert,
  AlertDescription as PrimitiveAlertDescription,
  AlertTitle as PrimitiveAlertTitle,
} from "@/components/ui/alert"
import { component } from "./component"
export const Alert = component(PrimitiveAlert, {})
export const AlertTitle = component(PrimitiveAlertTitle, {})
export const AlertDescription = component(PrimitiveAlertDescription, {}, "!text-foreground")

import {
  Avatar as PrimitiveAvatar,
  AvatarFallback as PrimitiveAvatarFallback,
  AvatarImage as PrimitiveAvatarImage,
} from "@/components/ui/avatar"
export const Avatar = component(PrimitiveAvatar, { profile: "size-16" })
export const AvatarImage = component(PrimitiveAvatarImage, {})
export const AvatarFallback = component(PrimitiveAvatarFallback, { profile: "text-xl" })

import {
  ButtonGroup as PrimitiveButtonGroup,
  ButtonGroupSeparator as PrimitiveButtonGroupSeparator,
  ButtonGroupText as PrimitiveButtonGroupText,
} from "@/components/ui/button-group"
export const ButtonGroup = component(PrimitiveButtonGroup, {})
export const ButtonGroupSeparator = component(PrimitiveButtonGroupSeparator, {})
export const ButtonGroupText = component(PrimitiveButtonGroupText, {})

import {
  Card as PrimitiveCard,
  CardAction as PrimitiveCardAction,
  CardContent as PrimitiveCardContent,
  CardDescription as PrimitiveCardDescription,
  CardFooter as PrimitiveCardFooter,
  CardHeader as PrimitiveCardHeader,
  CardTitle as PrimitiveCardTitle,
} from "@/components/ui/card"
export const Card = component(PrimitiveCard, {})
export const CardHeader = component(PrimitiveCardHeader, {})
export const CardFooter = component(PrimitiveCardFooter, {})
export const CardTitle = component(PrimitiveCardTitle, {})
export const CardAction = component(PrimitiveCardAction, {})
export const CardDescription = component(PrimitiveCardDescription, {})
export const CardContent = component(PrimitiveCardContent, {})

import { Checkbox as PrimitiveCheckbox } from "@/components/ui/checkbox"
export const Checkbox = component(PrimitiveCheckbox, {})

import {
  Dialog as PrimitiveDialog,
  DialogClose as PrimitiveDialogClose,
  DialogContent as PrimitiveDialogContent,
  DialogDescription as PrimitiveDialogDescription,
  DialogFooter as PrimitiveDialogFooter,
  DialogHeader as PrimitiveDialogHeader,
  DialogOverlay as PrimitiveDialogOverlay,
  DialogPortal as PrimitiveDialogPortal,
  DialogTitle as PrimitiveDialogTitle,
  DialogTrigger as PrimitiveDialogTrigger,
} from "@/components/ui/dialog"
export const Dialog = component(PrimitiveDialog, {})
export const DialogClose = component(PrimitiveDialogClose, {})
export const DialogContent = component(PrimitiveDialogContent, { compact: "sm:max-w-md" })
export const DialogDescription = component(PrimitiveDialogDescription, {})
export const DialogFooter = component(PrimitiveDialogFooter, { spaced: "mt-4" })
export const DialogHeader = component(PrimitiveDialogHeader, {})
export const DialogOverlay = component(PrimitiveDialogOverlay, {})
export const DialogPortal = component(PrimitiveDialogPortal, {})
export const DialogTitle = component(PrimitiveDialogTitle, {})
export const DialogTrigger = component(PrimitiveDialogTrigger, {})

import {
  DropdownMenu as PrimitiveDropdownMenu,
  DropdownMenuCheckboxItem as PrimitiveDropdownMenuCheckboxItem,
  DropdownMenuContent as PrimitiveDropdownMenuContent,
  DropdownMenuGroup as PrimitiveDropdownMenuGroup,
  DropdownMenuItem as PrimitiveDropdownMenuItem,
  DropdownMenuLabel as PrimitiveDropdownMenuLabel,
  DropdownMenuPortal as PrimitiveDropdownMenuPortal,
  DropdownMenuRadioGroup as PrimitiveDropdownMenuRadioGroup,
  DropdownMenuRadioItem as PrimitiveDropdownMenuRadioItem,
  DropdownMenuSeparator as PrimitiveDropdownMenuSeparator,
  DropdownMenuShortcut as PrimitiveDropdownMenuShortcut,
  DropdownMenuSub as PrimitiveDropdownMenuSub,
  DropdownMenuSubContent as PrimitiveDropdownMenuSubContent,
  DropdownMenuSubTrigger as PrimitiveDropdownMenuSubTrigger,
  DropdownMenuTrigger as PrimitiveDropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
export const DropdownMenu = component(PrimitiveDropdownMenu, {})
export const DropdownMenuPortal = component(PrimitiveDropdownMenuPortal, {})
export const DropdownMenuTrigger = component(PrimitiveDropdownMenuTrigger, {})
export const DropdownMenuContent = component(PrimitiveDropdownMenuContent, { create: "w-48", account: "w-52" })
export const DropdownMenuGroup = component(PrimitiveDropdownMenuGroup, {})
export const DropdownMenuItem = component(PrimitiveDropdownMenuItem, {
  destructive: "text-destructive focus:text-destructive",
})
export const DropdownMenuCheckboxItem = component(PrimitiveDropdownMenuCheckboxItem, {})
export const DropdownMenuRadioGroup = component(PrimitiveDropdownMenuRadioGroup, {})
export const DropdownMenuRadioItem = component(PrimitiveDropdownMenuRadioItem, {})
export const DropdownMenuLabel = component(PrimitiveDropdownMenuLabel, {})
export const DropdownMenuSeparator = component(PrimitiveDropdownMenuSeparator, {})
export const DropdownMenuShortcut = component(PrimitiveDropdownMenuShortcut, {})
export const DropdownMenuSub = component(PrimitiveDropdownMenuSub, {})
export const DropdownMenuSubTrigger = component(PrimitiveDropdownMenuSubTrigger, {})
export const DropdownMenuSubContent = component(PrimitiveDropdownMenuSubContent, {})

import {
  Form as PrimitiveForm,
  FormControl as PrimitiveFormControl,
  FormDescription as PrimitiveFormDescription,
  FormField as PrimitiveFormField,
  FormItem as PrimitiveFormItem,
  FormLabel as PrimitiveFormLabel,
  FormMessage as PrimitiveFormMessage,
} from "@/components/ui/form"
export const Form = PrimitiveForm
export const FormItem = component(PrimitiveFormItem, { inline: "flex items-center gap-3 space-y-0" })
export const FormLabel = component(PrimitiveFormLabel, { regular: "font-normal" })
export const FormControl = component(PrimitiveFormControl, {})
export const FormDescription = component(PrimitiveFormDescription, {})
export const FormMessage = component(PrimitiveFormMessage, { compact: "text-xs" })
export const FormField = PrimitiveFormField

import {
  Pagination as PrimitivePagination,
  PaginationContent as PrimitivePaginationContent,
  PaginationEllipsis as PrimitivePaginationEllipsis,
  PaginationItem as PrimitivePaginationItem,
  PaginationLink as PrimitivePaginationLink,
  PaginationNext as PrimitivePaginationNext,
  PaginationPrevious as PrimitivePaginationPrevious,
} from "@/components/ui/pagination"
export const Pagination = component(PrimitivePagination, {})
export const PaginationContent = component(PrimitivePaginationContent, {})
export const PaginationLink = component(PrimitivePaginationLink, {})
export const PaginationItem = component(PrimitivePaginationItem, {})
export const PaginationPrevious = component(PrimitivePaginationPrevious, {})
export const PaginationNext = component(PrimitivePaginationNext, {})
export const PaginationEllipsis = component(PrimitivePaginationEllipsis, {})

import {
  Select as PrimitiveSelect,
  SelectContent as PrimitiveSelectContent,
  SelectGroup as PrimitiveSelectGroup,
  SelectItem as PrimitiveSelectItem,
  SelectLabel as PrimitiveSelectLabel,
  SelectScrollDownButton as PrimitiveSelectScrollDownButton,
  SelectScrollUpButton as PrimitiveSelectScrollUpButton,
  SelectSeparator as PrimitiveSelectSeparator,
  SelectTrigger as PrimitiveSelectTrigger,
  SelectValue as PrimitiveSelectValue,
} from "@/components/ui/select"
export const Select = component(PrimitiveSelect, {})
export const SelectContent = component(PrimitiveSelectContent, {})
export const SelectGroup = component(PrimitiveSelectGroup, {})
export const SelectItem = component(PrimitiveSelectItem, {})
export const SelectLabel = component(PrimitiveSelectLabel, {})
export const SelectScrollDownButton = component(PrimitiveSelectScrollDownButton, {})
export const SelectScrollUpButton = component(PrimitiveSelectScrollUpButton, {})
export const SelectSeparator = component(PrimitiveSelectSeparator, {})
export const SelectTrigger = component(PrimitiveSelectTrigger, { pagination: "h-8 w-20" })
export const SelectValue = component(PrimitiveSelectValue, {})

import { Separator as PrimitiveSeparator } from "@/components/ui/separator"
export const Separator = component(PrimitiveSeparator, {})

import {
  Sheet as PrimitiveSheet,
  SheetClose as PrimitiveSheetClose,
  SheetContent as PrimitiveSheetContent,
  SheetDescription as PrimitiveSheetDescription,
  SheetFooter as PrimitiveSheetFooter,
  SheetHeader as PrimitiveSheetHeader,
  SheetTitle as PrimitiveSheetTitle,
  SheetTrigger as PrimitiveSheetTrigger,
} from "@/components/ui/sheet"
export const Sheet = component(PrimitiveSheet, {})
export const SheetTrigger = component(PrimitiveSheetTrigger, {})
export const SheetClose = component(PrimitiveSheetClose, {})
export const SheetContent = component(PrimitiveSheetContent, {}, "transition-transform")
export const SheetHeader = component(PrimitiveSheetHeader, {})
export const SheetFooter = component(PrimitiveSheetFooter, {})
export const SheetTitle = component(PrimitiveSheetTitle, {})
export const SheetDescription = component(PrimitiveSheetDescription, {})

import { Skeleton as PrimitiveSkeleton } from "@/components/ui/skeleton"
export const Skeleton = component(PrimitiveSkeleton, {
  short: "h-4 w-12",
  medium: "h-4 w-32",
  long: "h-4 w-48",
  title: "h-4 w-64",
  email: "h-4 w-40",
  action: "size-8 rounded-md",
  badge: "h-5 w-20 rounded-full",
  dot: "size-2 rounded-full",
  bar: "h-2 w-full",
  avatar: "repository-skeleton size-7 rounded-full",
  third: "repository-skeleton h-4 w-1/3",
  half: "h-4 w-1/2",
  trailing: "repository-skeleton ml-auto h-4 w-20",
  icon: "repository-skeleton size-4",
  fileTitle: "repository-skeleton h-4 w-48",
  fileMeta: "repository-skeleton h-4 w-36",
  fileSize: "ml-auto h-4 w-16",
  fileAction: "h-6 w-14",
  heading: "h-6 w-1/3",
  line: "h-4 w-full",
  paragraph: "h-4 w-2/3",
  codeShort: "repository-skeleton h-3 w-32 shrink-0",
  codeMedium: "repository-skeleton h-3 w-48 shrink-0",
  codeLong: "repository-skeleton h-3 w-64 shrink-0",
})

import { Toaster as PrimitiveToaster } from "@/components/ui/sonner"
export const Toaster = component(PrimitiveToaster, {}, "toaster group")

import {
  TableBody as PrimitiveTableBody,
  TableCaption as PrimitiveTableCaption,
  TableCell as PrimitiveTableCell,
  TableFooter as PrimitiveTableFooter,
  TableHead as PrimitiveTableHead,
  TableHeader as PrimitiveTableHeader,
  TableRow as PrimitiveTableRow,
} from "@/components/ui/table"

export const TableHeader = component(PrimitiveTableHeader, {})
export const TableBody = component(PrimitiveTableBody, {})
export const TableFooter = component(PrimitiveTableFooter, {})
export const TableHead = component(PrimitiveTableHead, {})
export const TableRow = component(PrimitiveTableRow, { static: "hover:bg-transparent" })
export const TableCell = component(PrimitiveTableCell, { empty: "h-32 text-center text-muted-foreground" })
export const TableCaption = component(PrimitiveTableCaption, {})

import {
  Tabs as PrimitiveTabs,
  TabsContent as PrimitiveTabsContent,
  TabsList as PrimitiveTabsList,
  TabsTrigger as PrimitiveTabsTrigger,
} from "@/components/ui/tabs"
export const Tabs = component(PrimitiveTabs, { spaced: "gap-4" })
export const TabsList = component(PrimitiveTabsList, {})
export const TabsTrigger = component(PrimitiveTabsTrigger, {})
export const TabsContent = component(PrimitiveTabsContent, { spaced: "space-y-4" })

import {
  Tooltip as PrimitiveTooltip,
  TooltipContent as PrimitiveTooltipContent,
  TooltipProvider as PrimitiveTooltipProvider,
  TooltipTrigger as PrimitiveTooltipTrigger,
} from "@/components/ui/tooltip"
export const Tooltip = component(PrimitiveTooltip, {})
export const TooltipTrigger = component(PrimitiveTooltipTrigger, {})
export const TooltipContent = component(PrimitiveTooltipContent, {})
export const TooltipProvider = component(PrimitiveTooltipProvider, {})
