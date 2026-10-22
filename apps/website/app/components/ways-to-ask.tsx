import { Icons } from "@stark/ui/components/icons";
import { LogoMark } from "@stark/ui/components/logo";
import { useState } from "react";

const doors = [
  {
    id: "tg",
    label: "Telegram voice notes",
    text: "Hold the mic in Telegram and say what you need: “top up 5k”, “buy 2GB for my line”, “how much did I spend this month?” The token comes back as text.",
  },
  {
    id: "wall",
    label: "Talk button on the wall",
    text: "Turn a spare Android phone into a meter-side speaker. Open the Talk page, add it to your home screen and press one big button. The phone holds no money.",
  },
];

export function WaysToAsk() {
  const [door, setDoor] = useState(doors[0]!.id);
  const current = doors.find((d) => d.id === door)!;
  return (
    <section
      id="how"
      className="mx-auto flex max-w-[1240px] scroll-mt-20 flex-col items-center gap-8 px-4 py-24 text-center sm:px-6 sm:py-[120px]"
    >
      <h2 className="m-0 font-serif text-[clamp(34px,3.6vw,48px)] leading-[1.05] font-normal tracking-[-0.015em]">
        However you ask, it pays
      </h2>
      <div className="relative h-[520px] w-full max-w-[960px] overflow-hidden rounded-2xl bg-[linear-gradient(135deg,#F6C9A6_0%,#F08A4B_35%,#C2410C_65%,#5A1E06_100%)] text-left sm:h-[460px]">
        <div
          aria-hidden="true"
          className="absolute -bottom-40 -left-25 h-[300px] w-[700px] rounded-full bg-white opacity-35 blur-[80px]"
        />
        <div className="absolute inset-x-0 top-0 flex h-7 items-center justify-between bg-white/35 px-3.5 text-xs text-ink">
          <span className="font-semibold">Stark</span>
          <span>Mon Oct 20 · 9:41 PM</span>
        </div>

        <div className="absolute top-14 right-4 left-4 flex h-[260px] flex-col overflow-hidden rounded-xl bg-white shadow-[0_20px_50px_rgba(15,17,21,0.25)] sm:right-auto sm:left-10 sm:h-[360px] sm:w-[340px]">
          <div className="flex items-center gap-1.5 border-b border-[#EEECE6] px-3 py-2.5">
            <span className="size-2.5 rounded-full bg-[#FF5F57]" />
            <span className="size-2.5 rounded-full bg-[#FEBC2E]" />
            <span className="size-2.5 rounded-full bg-[#28C840]" />
            <span className="ml-2.5 text-xs font-semibold">Telegram · Stark</span>
          </div>
          <div className="flex flex-1 flex-col gap-2 p-3.5 text-xs leading-[1.4]">
            <span className="self-end rounded-[12px_12px_4px_12px] bg-brand px-2.5 py-[7px] text-white">
              Voice note · 0:04 · “top up the house 5k”
            </span>
            <span className="self-start rounded-[12px_12px_12px_4px] bg-bubble px-2.5 py-[7px]">
              Home meter, ₦5,000. Go ahead?
            </span>
            <span className="self-end rounded-[12px_12px_4px_12px] bg-brand px-2.5 py-[7px] text-white">
              yes
            </span>
            <span className="flex flex-col gap-1 self-start rounded-[12px_12px_12px_4px] bg-bubble px-2.5 py-2">
              <strong className="font-semibold">Your token is ready</strong>
              <span className="tabular">4821 0937 5512 8846 3019</span>
              <span className="text-ink-3">₦7,000 left of this month’s limit</span>
            </span>
          </div>
        </div>

        <div className="absolute right-6 bottom-6 flex h-[200px] w-[150px] flex-col items-center justify-center gap-3 rounded-[28px] border-[6px] border-canvas-deep bg-canvas text-fg shadow-[0_20px_50px_rgba(15,17,21,0.35)] sm:top-24 sm:right-15 sm:bottom-auto sm:h-[330px] sm:w-[220px] sm:gap-3.5">
          <span className="text-[11px] text-muted-foreground">Wall phone · Home</span>
          <span className="flex size-16 items-center justify-center rounded-full bg-brand text-white shadow-[0_0_0_10px_rgba(194,65,12,0.25)] sm:size-24">
            <Icons.Mic size={32} />
          </span>
          <span className="font-serif text-lg sm:text-xl">Listening…</span>
        </div>

        <div className="absolute top-10 right-6 hidden w-[280px] items-center gap-2.5 rounded-[14px] bg-white/92 px-3 py-2.5 text-xs leading-[1.35] shadow-[0_10px_30px_rgba(15,17,21,0.2)] sm:flex">
          <span className="flex size-[30px] flex-none items-center justify-center rounded-lg bg-brand">
            <LogoMark size={18} cutout="#C2410C" className="[&_path:first-child]:fill-white" />
          </span>
          <span className="flex-1">
            <strong className="block font-semibold">Paid</strong>
            Home meter, ₦5,000. Token sent to Telegram.
          </span>
          <span className="self-start text-ink-3">now</span>
        </div>
      </div>

      <div
        role="tablist"
        aria-label="Ways to ask"
        className="flex flex-wrap justify-center gap-1 rounded-full bg-white p-1 text-[13px] shadow-[0_2px_10px_rgba(15,17,21,0.06)]"
      >
        {doors.map((d) => (
          <button
            key={d.id}
            type="button"
            role="tab"
            aria-selected={d.id === door}
            onClick={() => setDoor(d.id)}
            className={`min-h-9 cursor-pointer rounded-full border-0 px-3.5 py-2 text-ink ${d.id === door ? "bg-brand-swash font-medium" : "bg-transparent"}`}
          >
            {d.label}
          </button>
        ))}
      </div>
      <p className="m-0 max-w-[560px] text-sm text-ink-2" role="tabpanel">
        {current.text}
      </p>
    </section>
  );
}
