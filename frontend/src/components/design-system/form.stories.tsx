import type { Meta, StoryObj } from "@storybook/react-vite"
import { useForm } from "react-hook-form"
import {
  Button,
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
  Input,
} from "@/components/design-system"

const meta = { title: "Components/Form" } satisfies Meta
export default meta
type Story = StoryObj
const RepositoryForm = ({ disabled = false }: { disabled?: boolean }) => {
  const form = useForm({ defaultValues: { name: "" } })
  return (
    <Form {...form}>
      <form className="grid max-w-md gap-4" onSubmit={form.handleSubmit(() => {})}>
        <FormField
          control={form.control}
          name="name"
          rules={{
            required: "Repository name is required",
            pattern: { value: /^[a-z\d._-]+$/i, message: "Use letters, numbers, dots, underscores, or hyphens" },
          }}
          render={({ field }) => (
            <FormItem>
              <FormLabel>Repository name</FormLabel>
              <FormControl>
                <Input {...field} disabled={disabled} placeholder="my-awesome-project" />
              </FormControl>
              <FormDescription>A short name for your project.</FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />
        <Button type="submit" disabled={disabled}>
          Create repository
        </Button>
      </form>
    </Form>
  )
}
export const Default: Story = { render: () => <RepositoryForm /> }
export const Disabled: Story = { render: () => <RepositoryForm disabled /> }
