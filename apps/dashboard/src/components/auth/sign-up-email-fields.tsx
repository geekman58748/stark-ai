import { Field } from "@/components/auth/field";
import { PasswordField } from "@/components/auth/password-field";

export type SignUpDetails = {
  first: string;
  last: string;
  email: string;
  password: string;
};

export function SignUpEmailFields({
  details,
  onChange,
}: {
  details: SignUpDetails;
  onChange: (details: SignUpDetails) => void;
}) {
  return (
    <>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field
          label="First name"
          autoComplete="given-name"
          placeholder="Tunde"
          value={details.first}
          onChange={(first) => onChange({ ...details, first })}
        />
        <Field
          label="Last name"
          autoComplete="family-name"
          placeholder="Adebayo"
          value={details.last}
          onChange={(last) => onChange({ ...details, last })}
        />
      </div>
      <Field
        label="Email"
        type="email"
        autoComplete="email"
        placeholder="tunde@example.com"
        required
        value={details.email}
        onChange={(email) => onChange({ ...details, email })}
      />
      <PasswordField
        autoComplete="new-password"
        placeholder="At least 8 characters"
        value={details.password}
        onChange={(password) => onChange({ ...details, password })}
      />
    </>
  );
}
