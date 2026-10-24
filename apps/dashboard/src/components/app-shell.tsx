import { stateQuery } from "@stark/api";
import { Avatar, AvatarFallback } from "@stark/ui/components/avatar";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@stark/ui/components/breadcrumb";
import { Button } from "@stark/ui/components/button";
import { Icons } from "@stark/ui/components/icons";
import { LogoMark } from "@stark/ui/components/logo";
import { cn } from "@stark/ui/utils/cn";
import { useQuery } from "@tanstack/react-query";
import { Link, useRouterState } from "@tanstack/react-router";
import type { ReactNode } from "react";

const tabs = [
  { to: "/", label: "Home", icon: Icons.Home, exact: true },
  { to: "/bills", label: "Bills", icon: Icons.Bills, exact: false },
  { to: "/activity", label: "Activity", icon: Icons.Activity, exact: false },
  { to: "/wallet", label: "Wallet", icon: Icons.Wallet, exact: false },
  { to: "/settings", label: "Settings", icon: Icons.Settings, exact: false },
] as const;

const pageNames: [string, string][] = [
  ["/bills", "Bills"],
  ["/pay", "Pay a bill"],
  ["/activity", "Activity"],
  ["/wallet", "Wallet"],
  ["/settings", "Settings"],
];

function usePath() {
  return useRouterState({ select: (s) => s.location.pathname });
}

function isActive(path: string, to: string, exact: boolean) {
  return exact ? path === to : path === to || path.startsWith(`${to}/`);
}

function AccountAvatar() {
  const { data } = useQuery(stateQuery());
  const initials = data?.first_name?.slice(0, 2).toUpperCase() ?? "";
  return (
    <Link to="/settings" aria-label="Account and settings" className="rounded-full no-underline">
      <Avatar className="size-8.5">
        <AvatarFallback className="bg-surface-3 text-xs font-semibold text-fg">
          {initials}
        </AvatarFallback>
      </Avatar>
    </Link>
  );
}

function Header() {
  const path = usePath();
  const page = pageNames.find(([p]) => isActive(path, p, false))?.[1] ?? "Home";
  return (
    <header className="sticky top-0 z-10 flex items-center gap-3 border-b border-white/8 bg-canvas/92 px-4 pt-[max(12px,env(safe-area-inset-top))] pb-2.5 backdrop-blur-lg sm:border-line sm:px-5 sm:py-3.5">
      <Breadcrumb>
        <BreadcrumbList className="gap-3 text-fg">
          <BreadcrumbItem>
            <BreadcrumbLink
              render={<Link to="/" aria-label="Stark home" />}
              className="flex items-center gap-2 text-fg no-underline"
            >
              <LogoMark />
              <span className="text-base font-semibold sm:text-[15px]">Stark</span>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator className="hidden text-faint sm:inline">/</BreadcrumbSeparator>
          <BreadcrumbItem className="hidden sm:inline-flex">
            <BreadcrumbPage className="text-[13px] font-medium">{page}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      <div className="ml-auto flex items-center gap-2 sm:gap-2.5">
        <Button
          size="sm"
          nativeButton={false}
          render={<Link to="/pay" aria-label="Pay a bill" />}
          className="size-9.5 px-0 sm:size-auto sm:px-4"
        >
          <Icons.Add size={14} />
          <span className="hidden sm:inline">Pay a bill</span>
        </Button>
        <AccountAvatar />
      </div>
    </header>
  );
}

function Dock() {
  const path = usePath();
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-4 z-10 hidden justify-center gap-2 sm:flex">
      <nav
        aria-label="App"
        className="pointer-events-auto flex gap-0.5 rounded-full border border-white/10 bg-dock p-1.25 shadow-[0_12px_30px_rgba(0,0,0,0.5)]"
      >
        {tabs.map(({ to, label, icon: Icon, exact }) => (
          <Link
            key={to}
            to={to}
            aria-label={label}
            aria-current={isActive(path, to, exact) ? "page" : undefined}
            className={cn(
              "flex size-10.5 items-center justify-center rounded-full text-fg",
              isActive(path, to, exact) && "bg-brand/25",
            )}
          >
            <Icon size={18} />
          </Link>
        ))}
      </nav>
      <Link
        to="/talk"
        aria-label="Talk to Stark"
        className="pointer-events-auto flex size-13.5 items-center justify-center rounded-full bg-brand text-white shadow-[0_12px_30px_rgba(0,0,0,0.5)]"
      >
        <Icons.Mic size={22} />
      </Link>
    </div>
  );
}

function TabBar() {
  const path = usePath();
  const [home, bills, activity, wallet] = tabs;
  const item = ({ to, label, icon: Icon, exact }: (typeof tabs)[number]) => (
    <Link
      key={to}
      to={to}
      aria-current={isActive(path, to, exact) ? "page" : undefined}
      className={cn(
        "flex flex-1 flex-col items-center gap-1 py-2 text-[11px] font-medium no-underline",
        isActive(path, to, exact) ? "text-brand-soft" : "text-idle hover:text-fg",
      )}
    >
      <Icon size={22} />
      {label}
    </Link>
  );
  return (
    <nav
      aria-label="App"
      className="sticky bottom-0 z-10 flex items-start border-t border-white/8 bg-surface/92 px-2 pt-1 pb-[max(22px,env(safe-area-inset-bottom))] backdrop-blur-lg sm:hidden"
    >
      {item(home)}
      {item(bills)}
      <Link to="/talk" aria-label="Talk to Stark" className="flex flex-1 justify-center">
        <span className="-mt-5.5 flex size-14 items-center justify-center rounded-full border-4 border-canvas bg-brand text-white shadow-[0_8px_24px_rgba(194,65,12,0.45)]">
          <Icons.Mic size={24} />
        </span>
      </Link>
      {item(activity)}
      {item(wallet)}
    </nav>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col">
      <Header />
      <main className="mx-auto flex w-full max-w-190 flex-1 flex-col gap-5 px-4 pt-3 pb-7 sm:px-5 sm:pt-9 sm:pb-28">
        {children}
      </main>
      <Dock />
      <TabBar />
    </div>
  );
}

export function PageTitle({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <h1 className="m-0 font-serif text-[34px] leading-[1.1] font-medium tracking-[-0.01em]">
        {children}
      </h1>
      {aside ? <div className="ml-auto">{aside}</div> : null}
    </div>
  );
}

export function BackLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Button
      variant="ghost"
      size="sm"
      nativeButton={false}
      render={<Link to={to} />}
      className="-ml-1 self-start px-1"
    >
      <Icons.ChevronLeft size={16} />
      {children}
    </Button>
  );
}
