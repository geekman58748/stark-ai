import { buttonVariants } from "@stark/ui/components/button";
import { Icons } from "@stark/ui/components/icons";
import { LogoMark } from "@stark/ui/components/logo";
import { cn } from "@stark/ui/utils/cn";
import { type CSSProperties, useEffect, useRef, useState } from "react";
import { links } from "~/lib/links";

const floaters = [
  {
    icon: Icons.Electricity,
    className: "left-[6%] top-10 size-[72px] -rotate-8",
    enter: "0ms",
    drift: "11s",
  },
  {
    icon: Icons.Airtime,
    className: "right-[7%] top-[30px] size-[72px] rotate-10",
    enter: "70ms",
    drift: "13.5s",
  },
  { icon: Icons.Tv, className: "left-[12%] bottom-[120px] size-14", enter: "140ms", drift: "9.5s" },
  {
    icon: Icons.Data,
    className: "right-[12%] bottom-[130px] size-14 -rotate-6",
    enter: "210ms",
    drift: "12.5s",
  },
];

/** Three true things, one at a time. The first line is the one reduced motion keeps. */
const statuses = ["Voice ready · Daniel", "Dry-run · nothing charged", "Built on NEAR"];

/** The rulebook, scrolling under the pill. The safety section says the same three things. */
const rules = ["a limit it can’t cross", "bills, and nothing else", "a receipt for every naira"];

const marqueeCopies = 8;

export function Closing() {
  const ref = useRef<HTMLElement>(null);
  // The section sits below the fold, so the markup starts visible: on mount the
  // observer arms the chips into their hidden state and then reveals them once
  // the section is in view. No JS means no arming either — the chips stay put.
  const [phase, setPhase] = useState<"idle" | "armed" | "in">("idle");

  useEffect(() => {
    const node = ref.current;
    if (!node || typeof IntersectionObserver === "undefined") {
      setPhase("in");
      return;
    }

    setPhase("armed");
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry?.isIntersecting) return;
        setPhase("in");
        observer.disconnect();
      },
      { rootMargin: "0px 0px -12% 0px" },
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return (
    <section
      ref={ref}
      className={cn(
        "closing relative overflow-hidden bg-[#F7F6F2] bg-[linear-gradient(#E9E7E0_1px,transparent_1px),linear-gradient(90deg,#E9E7E0_1px,transparent_1px)] bg-size-[32px_32px]",
        phase === "armed" && "is-armed",
        phase === "in" && "is-in",
      )}
    >
      <div className="relative mx-auto flex max-w-[720px] flex-col items-center gap-7 px-4 pt-28 pb-44 text-center sm:px-6 sm:pt-[120px] sm:pb-[180px]">
        <h2 className="relative z-0 m-0 font-serif text-[clamp(30px,4.4vw,60px)] leading-[1.08] font-normal tracking-[-0.02em]">
          Keep the lights on,
          <br />
          <span className="swash">without leaving the chat</span>
        </h2>
        <span className="flex items-center gap-2.5">
          <span className="glint">
            <LogoMark size={34} cutout="#F7F6F2" glint />
          </span>
          <span className="text-[26px] font-semibold tracking-[-0.01em]">Stark</span>
        </span>
        <div className="flex flex-wrap justify-center gap-2 text-[13px]">
          <a href={links.getStarted} className={cn(buttonVariants({ variant: "ink" }), "min-h-10")}>
            Get started
          </a>
          <a href={links.telegram} className={cn(buttonVariants({ variant: "paper" }), "min-h-10")}>
            Open the Telegram bot
          </a>
        </div>
      </div>
      {floaters.map(({ icon: Icon, className, enter, drift }) => (
        <span
          key={className}
          aria-hidden="true"
          style={{ "--enter": enter, "--drift": drift } as CSSProperties}
          className={cn(
            "floater absolute hidden items-center justify-center rounded-full bg-white text-brand shadow-[0_4px_12px_rgba(15,17,21,0.12)] sm:flex",
            className,
          )}
        >
          <Icon size={26} />
        </span>
      ))}
      <div className="marquee bottom-[118px] font-mono text-[10.5px] tracking-[0.2em] text-ink-2/60 uppercase sm:bottom-[92px]">
        <div className="marquee-track">
          {Array.from({ length: marqueeCopies }, (_, copy) => (
            <span key={copy} aria-hidden={copy > 0 || undefined} className="marquee-set">
              {rules.map((rule) => (
                <span key={rule} className="marquee-line">
                  {rule}
                </span>
              ))}
            </span>
          ))}
        </div>
      </div>
      <footer className="absolute inset-x-4 bottom-6 mx-auto flex max-w-[1240px] flex-wrap items-center justify-between gap-3 rounded-full border border-white/70 bg-white/42 px-6 py-3.5 text-xs text-ink-2 shadow-[0_8px_30px_rgba(15,17,21,0.08)] backdrop-blur-lg backdrop-saturate-140 sm:inset-x-6">
        <span className="powerline" aria-hidden="true" />
        <span className="flex items-center gap-2">
          <span aria-hidden="true" className="status-dot size-1.5 rounded-full bg-brand-warm" />
          <span className="status-rail">
            {statuses.map((status) => (
              <span key={status} className="status-line">
                {status}
              </span>
            ))}
          </span>
        </span>
        <span className="flex gap-5">
          <a href="#faq" className="sweep-link text-ink-2">
            FAQ
          </a>
          <a href={links.telegram} className="sweep-link text-ink-2">
            Telegram
          </a>
        </span>
      </footer>
    </section>
  );
}
