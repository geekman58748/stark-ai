import { buttonVariants } from "@stark/ui/components/button";
import { Icons } from "@stark/ui/components/icons";
import { LogoMark } from "@stark/ui/components/logo";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@stark/ui/components/sheet";
import { cn } from "@stark/ui/utils/cn";
import { useState } from "react";
import { links } from "~/lib/links";

const nav = [
  { href: "#how", label: "How it works" },
  { href: "#bills", label: "Bills" },
  { href: "#safety", label: "Safety" },
  { href: "#fund", label: "Funding" },
  { href: "#faq", label: "FAQ" },
];

export function SiteHeader() {
  const [open, setOpen] = useState(false);
  return (
    <header className="sticky top-0 z-20 bg-paper/85 backdrop-blur-md lg:static lg:bg-transparent lg:backdrop-blur-none">
      <div className="mx-auto flex max-w-[1240px] items-center gap-6 px-4 py-2.5 lg:px-6 lg:py-4">
        <a href="/" className="flex items-center gap-2 text-ink no-underline">
          <LogoMark cutout="#F4F2EC" />
          <span className="text-[17px] font-semibold tracking-[-0.01em] lg:text-[19px]">Stark</span>
        </a>
        <nav aria-label="Main" className="hidden gap-1 text-[15px] lg:flex">
          {nav.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="rounded-[10px] px-3.5 py-2 text-ink no-underline hover:bg-paper-2"
            >
              {item.label}
            </a>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-2.5 text-[15px] lg:gap-4">
          <a href={links.logIn} className="hidden text-ink no-underline lg:inline">
            Log in
          </a>
          <a
            href={links.getStarted}
            className={cn(
              buttonVariants({ variant: "ink", size: "md" }),
              "min-h-10 lg:min-h-11 lg:text-[15px]",
            )}
          >
            Get started
            <Icons.ArrowRight size={16} className="hidden lg:block" />
          </a>
          <Sheet open={open} onOpenChange={setOpen}>
            <SheetTrigger
              aria-label="Menu"
              className={cn(
                buttonVariants({ variant: "outline", size: "icon" }),
                "border-[#D9D6CC] bg-transparent text-ink lg:hidden",
              )}
            >
              <Icons.More size={18} />
            </SheetTrigger>
            <SheetContent side="top" className="bg-paper px-4 pt-4 pb-6">
              <SheetTitle className="flex items-center gap-2 font-sans text-base font-semibold">
                <LogoMark cutout="#F4F2EC" />
                Stark
              </SheetTitle>
              <nav aria-label="Main" className="flex flex-col gap-1">
                {[...nav, { href: links.logIn, label: "Log in" }].map((item) => (
                  <a
                    key={item.href}
                    href={item.href}
                    onClick={() => setOpen(false)}
                    className="rounded-xl px-3 py-3 text-base text-ink no-underline hover:bg-paper-2"
                  >
                    {item.label}
                  </a>
                ))}
              </nav>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </header>
  );
}
