import { Field } from "@/components/auth/field";
import { PasswordRevealButton } from "@/components/auth/password-reveal-button";
import { useState } from "react";

export function PasswordField({
  autoComplete,
  placeholder,
  value,
  onChange,
}: {
  autoComplete: "new-password" | "current-password";
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
}) {
  const [revealed, setRevealed] = useState(false);

  return (
    <Field
      label="Password"
      type={revealed ? "text" : "password"}
      autoComplete={autoComplete}
      placeholder={placeholder}
      required
      value={value}
      onChange={onChange}
      trailing={
        <PasswordRevealButton
          revealed={revealed}
          onToggle={() => setRevealed((was) => !was)}
        />
      }
    />
  );
}
