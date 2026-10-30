import { MethodPickerOption } from "@/components/auth/method-picker-option";
import { METHODS, type Method } from "@/components/auth/methods";

export function MethodPicker({
  label,
  value,
  onChange,
}: {
  label: string;
  value: Method;
  onChange: (method: Method) => void;
}) {
  return (
    <div role="group" aria-label={label} className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {METHODS.map((entry) => (
        <MethodPickerOption
          key={entry.id}
          method={entry.id}
          label={entry.label}
          active={entry.id === value}
          onSelect={onChange}
        />
      ))}
    </div>
  );
}
