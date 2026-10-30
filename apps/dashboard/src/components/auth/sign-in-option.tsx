import { Button } from "@stark/ui/components/button";
import type { ReactNode } from "react";
import { MethodIcon } from "@/components/auth/method-icon";
import type { Method } from "@/components/auth/methods";

export function SignInOption({
  method,
  tag,
  disabled,
  onClick,
  children,
}: {
  method: Method;
  tag?: string;
  disabled?: boolean;
  onClick?: () => void;
  children: ReactNode;
}) {
  return (
    <Button
      type="button"
      variant="outline"
      size="lg"
      block
      disabled={disabled}
      onClick={onClick}
      className="relative h-12 gap-2.5 font-medium"
    >
      <MethodIcon method={method} />
      {children}
      {tag ? (
        <span className="absolute right-5 text-[11px] font-normal text-faint">{tag}</span>
      ) : null}
    </Button>
  );
}
