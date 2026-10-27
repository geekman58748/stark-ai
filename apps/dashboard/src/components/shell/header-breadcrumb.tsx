import { usePath } from "@/components/shell/use-path";
import { NavMatch } from "@/lib/navigation/nav-match";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@stark/ui/components/breadcrumb";
import { LogoMark } from "@stark/ui/components/logo";
import { Link } from "@tanstack/react-router";

const pageNames: [string, string][] = [
  ["/bills", "Bills"],
  ["/connect", "Connect a chat"],
  ["/pay", "Pay a bill"],
  ["/activity", "Activity"],
  ["/wallet", "Wallet"],
  ["/settings", "Settings"],
];

export function HeaderBreadcrumb() {
  const path = usePath();
  const page =
    pageNames.find(([p]) => NavMatch.isActive(path, p, false))?.[1] ?? "Home";
  return (
    <Breadcrumb>
      <BreadcrumbList className="gap-3 text-fg">
        <BreadcrumbItem>
          <BreadcrumbLink
            render={<Link to="/" aria-label="Stark home" />}
            className="flex items-center gap-2 text-fg no-underline"
          >
            <LogoMark />
            <span className="text-base font-semibold sm:text-[15px]">
              Stark
            </span>
          </BreadcrumbLink>
        </BreadcrumbItem>
        <BreadcrumbSeparator className="hidden text-faint sm:inline">
          /
        </BreadcrumbSeparator>
        <BreadcrumbItem className="hidden sm:inline-flex">
          <BreadcrumbPage className="text-[13px] font-medium">
            {page}
          </BreadcrumbPage>
        </BreadcrumbItem>
      </BreadcrumbList>
    </Breadcrumb>
  );
}
