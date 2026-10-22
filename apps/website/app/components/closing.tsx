import { Icons } from "@stark/ui/icons";
import { LogoMark } from "@stark/ui/logo";
import { links } from "~/lib/links";

const floaters = [
  { icon: Icons.Electricity, className: "left-[6%] top-10 size-[72px] -rotate-8" },
  { icon: Icons.Airtime, className: "right-[7%] top-[30px] size-[72px] rotate-10" },
  { icon: Icons.Tv, className: "left-[12%] bottom-[120px] size-14" },
  { icon: Icons.Data, className: "right-[12%] bottom-[130px] size-14 -rotate-6" },
];

export function Closing() {
  return (
    <section className="relative overflow-hidden bg-[#F7F6F2] bg-[linear-gradient(#E9E7E0_1px,transparent_1px),linear-gradient(90deg,#E9E7E0_1px,transparent_1px)] bg-size-[32px_32px]">
      <div className="relative mx-auto flex max-w-[720px] flex-col items-center gap-7 px-4 pt-28 pb-44 text-center sm:px-6 sm:pt-[120px] sm:pb-[180px]">
        <h2 className="relative z-0 m-0 font-serif text-[clamp(30px,4.4vw,60px)] leading-[1.08] font-normal tracking-[-0.02em]">
          Keep the lights on,
          <br />
          <span className="swash">without leaving the chat</span>
        </h2>
        <span className="flex items-center gap-2.5">
          <LogoMark size={34} cutout="#F7F6F2" />
          <span className="text-[26px] font-semibold tracking-[-0.01em]">Stark</span>
        </span>
        <div className="flex flex-wrap justify-center gap-2 text-[13px]">
          <a
            href={links.getStarted}
            className="rounded-full bg-ink px-4 py-2.5 font-medium text-white no-underline"
          >
            Get started
          </a>
          <a
            href={links.telegram}
            className="rounded-full bg-paper-2 px-4 py-2.5 font-medium text-ink no-underline"
          >
            Open the Telegram bot
          </a>
        </div>
      </div>
      {floaters.map(({ icon: Icon, className }) => (
        <span
          key={className}
          aria-hidden="true"
          className={`absolute hidden items-center justify-center rounded-full bg-white text-brand shadow-[0_4px_12px_rgba(15,17,21,0.12)] sm:flex ${className}`}
        >
          <Icon size={26} />
        </span>
      ))}
      <footer className="absolute inset-x-4 bottom-6 mx-auto flex max-w-[1240px] flex-wrap items-center justify-between gap-3 rounded-full border border-white/70 bg-white/42 px-6 py-3.5 text-xs text-ink-2 shadow-[0_8px_30px_rgba(15,17,21,0.08)] backdrop-blur-lg backdrop-saturate-140 sm:inset-x-6">
        <span>Stark · Built on NEAR</span>
        <span className="flex gap-5">
          <a href="#faq" className="text-ink-2">
            FAQ
          </a>
          <a href={links.telegram} className="text-ink-2">
            Telegram
          </a>
        </span>
      </footer>
    </section>
  );
}
