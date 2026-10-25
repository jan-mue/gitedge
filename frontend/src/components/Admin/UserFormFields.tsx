import { useFormContext } from "react-hook-form"
import { Checkbox, FormControl, FormField, FormItem, FormLabel } from "@/components/design-system"
import { FormInputField } from "@/components/design-system/form"

type UserFields = {
  email: string
  display_name?: string
  password?: string
  confirm_password?: string
  is_superuser?: boolean
  is_active?: boolean
}

export const UserFormFields = ({ passwordRequired = false }: { passwordRequired?: boolean }) => {
  const { control } = useFormContext<UserFields>()
  return (
    <div className="grid gap-4 py-4">
      <FormInputField control={control} name="email" label="Email" placeholder="Email" type="email" required />
      <FormInputField control={control} name="display_name" label="Full Name" placeholder="Full name" />
      <FormInputField
        control={control}
        name="password"
        label="Set Password"
        placeholder="Password"
        type="password"
        required={passwordRequired}
      />
      <FormInputField
        control={control}
        name="confirm_password"
        label="Confirm Password"
        placeholder="Password"
        type="password"
        required={passwordRequired}
      />
      {(
        [
          ["is_superuser", "Is superuser?"],
          ["is_active", "Is active?"],
        ] as const
      ).map(([name, label]) => (
        <FormField
          key={name}
          control={control}
          name={name}
          render={({ field }) => (
            <FormItem appearance="inline">
              <FormControl>
                <Checkbox checked={field.value} onCheckedChange={field.onChange} />
              </FormControl>
              <FormLabel appearance="regular">{label}</FormLabel>
            </FormItem>
          )}
        />
      ))}
    </div>
  )
}
