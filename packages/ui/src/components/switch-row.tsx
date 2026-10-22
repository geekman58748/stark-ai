import { Switch } from "@stark/ui/components/switch";
import { type ReactNode, useId } from "react";

/** A setting with a title, an optional subtitle and an on/off switch. */
export function SwitchRow({
  checked,
  onChange,
  title,
  subtitle,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  title: ReactNode;
  subtitle?: ReactNode;
}) {
  const id = useId();
  return (
    <label
      htmlFor={id}
      className="flex w-full cursor-pointer items-center gap-3 rounded-row border border-border bg-card px-4 py-3 text-left"
    >
      <span className="flex flex-1 flex-col">
        <span className="font-medium">{title}</span>
        {subtitle ? <span className="text-xs text-muted-foreground">{subtitle}</span> : null}
      </span>
      <Switch id={id} checked={checked} onCheckedChange={onChange} />
    </label>
  );
}
