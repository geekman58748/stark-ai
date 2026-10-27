import type { Method } from "@/components/auth/methods";
import { Icons } from "@stark/ui/components/icons";

export function MethodIcon({ method }: { method: Method }) {
  switch (method) {
    case "google":
      return (
        <span aria-hidden="true" className="text-[13px] font-semibold">
          G
        </span>
      );
    case "phone":
      return <Icons.Phone size={15} />;
    case "telegram":
      return <Icons.Telegram size={15} />;
    case "email":
      return <Icons.Mail size={15} />;
  }
}
