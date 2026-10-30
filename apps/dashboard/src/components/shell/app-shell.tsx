import type { ReactNode } from "react";
import { AppHeader } from "@/components/shell/app-header";
import { Dock } from "@/components/shell/dock";
import { TabBar } from "@/components/shell/tab-bar";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col">
      <AppHeader />
      <main className="mx-auto flex w-full max-w-190 flex-1 flex-col gap-5 px-4 pt-3 pb-7 sm:px-5 sm:pt-9 sm:pb-28">
        {children}
      </main>
      <Dock />
      <TabBar />
    </div>
  );
}
