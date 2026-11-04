import { Button } from "@stark/ui/components/button";
import { LogoMark } from "@stark/ui/components/logo";
import { Link } from "@tanstack/react-router";

export function DemoHeader() {
  return (
    <header className="sticky top-0 z-10 flex items-center gap-3 border-b border-line bg-canvas/92 px-4 py-3 backdrop-blur-lg sm:px-5">
      <a
        href="https://hellostark.xyz"
        aria-label="Stark home"
        className="flex items-center gap-2 text-fg no-underline hover:text-fg"
      >
        <LogoMark />
        <span className="text-[15px] font-semibold">Stark</span>
      </a>
      <span aria-hidden="true" className="text-faint">
        /
      </span>
      <span className="text-[13px] font-medium">Sample account</span>
      <div className="ml-auto flex items-center gap-2">
        <Button variant="ghost" nativeButton={false} render={<Link to="/login" />}>
          Log in
        </Button>
        <Button variant="brand" nativeButton={false} render={<Link to="/start" />}>
          Get started
        </Button>
      </div>
    </header>
  );
}
