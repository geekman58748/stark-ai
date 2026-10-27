import { DockTab } from "@/components/shell/dock-tab";
import { DockTalkLink } from "@/components/shell/dock-talk-link";
import { tabs } from "@/components/shell/tabs";

export function Dock() {
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-4 z-10 hidden justify-center gap-2 sm:flex">
      <nav
        aria-label="App"
        className="pointer-events-auto flex gap-0.5 rounded-full border border-white/10 bg-dock p-1.25 shadow-[0_12px_30px_rgba(0,0,0,0.5)]"
      >
        {tabs.map((tab) => (
          <DockTab key={tab.to} tab={tab} />
        ))}
      </nav>
      <DockTalkLink />
    </div>
  );
}
