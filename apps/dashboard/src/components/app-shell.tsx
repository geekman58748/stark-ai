import { stateQuery } from "@stark/api";
import { Avatar, AvatarFallback } from "@stark/ui/components/avatar";
import { buttonVariants } from "@stark/ui/components/button";
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
      <Avatar className="size-[34px]">
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
    <header className="flex items-center gap-3 px-4 pt-3 pb-2.5 sm:border-b sm:border-line sm:px-5 sm:py-3.5">
      <Link
        to="/"
        aria-label="Stark home"
        className="flex items-center gap-2 text-fg no-underline hover:text-fg"
      >
        <LogoMark />
        <span className="text-base font-semibold sm:text-[15px]">Stark</span>
      </Link>
      <span aria-hidden="true" className="hidden text-faint sm:inline">
        /
      </span>
      <span className="hidden text-[13px] font-medium sm:inline">{page}</span>
      <div className="ml-auto flex items-center gap-2 sm:gap-2.5">
        <Link
          to="/pay"
          aria-label="Pay a bill"
          className={cn(
            buttonVariants({ size: "sm" }),
            "size-[38px] px-0 text-white hover:text-white sm:size-auto sm:px-4",
          )}
        >
          <Icons.Add size={14} />
          <span className="hidden sm:inline">Pay a bill</span>
        </Link>
        <AccountAvatar />
      </div>
    </header>
  );
}

/** Desktop: a floating pill dock with the Talk button beside it. */
function Dock() {
  const path = usePath();
  return (
    <div className="pointer-events-none sticky bottom-4 mt-4 hidden justify-center gap-2 sm:flex">
      <nav
        aria-label="App"
        className="pointer-events-auto flex gap-0.5 rounded-full border border-white/10 bg-dock p-[5px] shadow-[0_12px_30px_rgba(0,0,0,0.5)]"
      >
        {tabs.map(({ to, label, icon: Icon, exact }) => (
          <Link
            key={to}
            to={to}
            aria-label={label}
            aria-current={isActive(path, to, exact) ? "page" : undefined}
            className={cn(
              "flex size-[42px] items-center justify-center rounded-full text-fg hover:text-fg",
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
        className="pointer-events-auto flex size-[54px] items-center justify-center rounded-full bg-brand text-white shadow-[0_12px_30px_rgba(0,0,0,0.5)] hover:text-white"
      >
        <Icons.Mic size={22} />
      </Link>
    </div>
  );
}

/** Phone: a blurred bottom tab bar with a raised Talk button in the middle. */
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
        isActive(path, to, exact)
          ? "text-brand-soft hover:text-brand-soft"
          : "text-idle hover:text-fg",
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
        <span className="-mt-[22px] flex size-14 items-center justify-center rounded-full border-4 border-canvas bg-brand text-white shadow-[0_8px_24px_rgba(194,65,12,0.45)]">
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
      <main className="mx-auto flex w-full max-w-[760px] flex-1 flex-col gap-5 px-4 pt-3 pb-7 sm:px-5 sm:pt-9 sm:pb-6">
        {children}
        <Dock />
      </main>
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
    <Link
      to={to}
      className="flex items-center gap-1.5 self-start text-[13px] text-fg-2 no-underline hover:text-fg"
    >
      <Icons.ChevronLeft size={16} />
      {children}
    </Link>
  );
}
