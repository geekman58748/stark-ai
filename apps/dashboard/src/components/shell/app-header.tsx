import { AccountAvatar } from "@/components/shell/account-avatar";
import { HeaderBreadcrumb } from "@/components/shell/header-breadcrumb";
import { PayBillButton } from "@/components/shell/pay-bill-button";

export function AppHeader() {
  return (
    <header className="sticky top-0 z-10 flex items-center gap-3 border-b border-white/8 bg-canvas/92 px-4 pt-[max(12px,env(safe-area-inset-top))] pb-2.5 backdrop-blur-lg sm:border-line sm:px-5 sm:py-3.5">
      <HeaderBreadcrumb />
      <div className="ml-auto flex items-center gap-2 sm:gap-2.5">
        <PayBillButton />
        <AccountAvatar />
      </div>
    </header>
  );
}
