import { Icons } from "@stark/ui/icons";
import { type ReactNode, useRef, useState } from "react";

const panel =
  "w-full max-w-[440px] rounded-[18px] bg-[#141518] text-sm text-fg shadow-[0_30px_60px_rgba(0,0,0,0.45)]";

function Toggle({ on }: { on: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={`relative h-[22px] w-[38px] flex-none rounded-full ${on ? "bg-brand" : "bg-[#3A3B40]"}`}
    >
      <span
        className={`absolute top-[3px] size-4 rounded-full ${on ? "right-[3px] bg-white" : "left-[3px] bg-[#8F939A]"}`}
      />
    </span>
  );
}

const rules: { title: string; body: string; bg: string; demo: ReactNode }[] = [
  {
    title: "A limit it can’t cross",
    body: "You set how much Stark may spend in a month and at once. Anything over is refused, and Stark offers what it can pay instead.",
    bg: "bg-[radial-gradient(60%_50%_at_20%_15%,#E9B98E_0%,rgba(233,185,142,0)_70%),radial-gradient(50%_60%_at_85%_80%,#6B2E12_0%,rgba(107,46,18,0)_70%),linear-gradient(160deg,#C9875A_0%,#8E4421_55%,#4A1F0D_100%)]",
    demo: (
      <div className={`${panel} flex flex-col gap-3.5 p-[18px]`}>
        <div className="flex justify-between text-[13px] text-[#B9BCC2]">
          <span>Spent this month</span>
          <span className="text-fg">₦23,000 of ₦30,000</span>
        </div>
        <div className="h-1.5 rounded-full bg-track">
          <div className="h-full w-[77%] rounded-full bg-brand-warm" />
        </div>
        <div className="self-end rounded-[14px_14px_4px_14px] bg-brand px-3 py-2 text-white">
          Top up ₦15,000
        </div>
        <div className="max-w-[85%] self-start rounded-[14px_14px_14px_4px] bg-[#24262B] px-3 py-2.5">
          That’s over your ₦10,000 limit for one payment. Pay ₦10,000 instead?
        </div>
        <div className="flex gap-2 text-[13px]">
          <span className="rounded-full bg-fg px-3 py-1.5 font-medium text-[#141414]">
            Pay ₦10,000
          </span>
          <span className="rounded-full border border-white/18 px-3 py-1.5">Cancel</span>
        </div>
      </div>
    ),
  },
  {
    title: "It can pay bills, and nothing else",
    body: "Stark can’t move your money anywhere except to the bills you added. Pause it or switch it off in one tap.",
    bg: "bg-[radial-gradient(55%_55%_at_80%_20%,#F2C9A1_0%,rgba(242,201,161,0)_70%),radial-gradient(60%_60%_at_10%_90%,#7A3416_0%,rgba(122,52,22,0)_70%),linear-gradient(200deg,#E3A876_0%,#B9663A_50%,#5C2810_100%)]",
    demo: (
      <div className={`${panel} overflow-hidden`}>
        <div className="flex items-center justify-between border-b border-white/8 px-[18px] py-3.5">
          <span className="font-medium">What Stark can do</span>
        </div>
        <div className="flex flex-col px-[18px] pt-2 pb-[18px]">
          {[
            ["Pay your bills", "Home, My line, Living room TV", true],
            ["Send money to people", "Never allowed", false],
            ["Change your limits", "Only you can", false],
          ].map(([t, s, on]) => (
            <div
              key={t as string}
              className="flex items-center justify-between border-b border-white/6 py-3.5 last:border-0"
            >
              <span className="flex flex-col">
                <span>{t}</span>
                <span className="text-xs text-[#8F939A]">{s}</span>
              </span>
              <Toggle on={on as boolean} />
            </div>
          ))}
        </div>
      </div>
    ),
  },
  {
    title: "A receipt for every naira",
    body: "Each payment keeps a receipt with its token, so you can always see what was paid, when and why.",
    bg: "bg-[radial-gradient(50%_50%_at_30%_80%,#EBC097_0%,rgba(235,192,151,0)_70%),radial-gradient(50%_60%_at_90%_10%,#5A260F_0%,rgba(90,38,15,0)_70%),linear-gradient(120deg,#A5532A_0%,#D69468_50%,#6E3015_100%)]",
    demo: (
      <div className={`${panel} overflow-hidden`}>
        <div className="flex items-center justify-between border-b border-white/8 px-[18px] py-3.5">
          <span className="font-medium">Receipts</span>
          <span className="text-xs text-[#8F939A]">October</span>
        </div>
        <div className="flex flex-col gap-0.5 p-2">
          {[
            ["21:41", "Home electricity · ₦5,000", "4821 0937 5512 8846 3019", "Paid"],
            ["21:40", "Home electricity · ₦15,000", null, "Declined"],
            ["08:15", "My line airtime · ₦1,000", null, "Paid"],
            ["Oct 12", "Added money · ₦20,000", null, "In"],
          ].map(([time, what, token, status], i) => (
            <div
              key={time}
              className={`flex gap-3 rounded-[10px] p-2.5 ${i === 0 ? "bg-[#24262B]" : ""}`}
            >
              <span className="tabular w-11 text-xs text-[#8F939A]">{time}</span>
              <span className="flex flex-1 flex-col">
                <span>{what}</span>
                {token ? <span className="tabular text-xs text-brand-soft">{token}</span> : null}
              </span>
              <span
                className={`text-xs ${status === "Paid" ? "text-brand-warm" : "text-[#8F939A]"}`}
              >
                {status}
              </span>
            </div>
          ))}
        </div>
      </div>
    ),
  },
  {
    title: "It asks before it pays",
    body: "Stark warns you before a meter runs out or a bill falls due, then waits for your yes. Nothing happens behind your back.",
    bg: "bg-[radial-gradient(55%_50%_at_70%_80%,#F0B98A_0%,rgba(240,185,138,0)_70%),radial-gradient(50%_60%_at_15%_15%,#62290F_0%,rgba(98,41,15,0)_70%),linear-gradient(170deg,#B8602F_0%,#E09A68_55%,#7B3516_100%)]",
    demo: (
      <div className={`${panel} overflow-hidden`}>
        <div className="flex items-center justify-between border-b border-white/8 px-[18px] py-3.5">
          <span className="font-medium">Stark</span>
          <span className="text-xs text-[#8F939A]">Telegram</span>
        </div>
        <div className="flex flex-col gap-2.5 p-3.5 text-[13px]">
          <div className="flex max-w-[85%] flex-col gap-1.5 self-start rounded-[14px_14px_14px_4px] bg-[#24262B] px-3 py-2.5">
            <span className="text-[11px] text-[#8F939A]">Stark · 8:02 PM</span>
            <span>Home meter has about 4 days left. Top up ₦5,000?</span>
            <span className="flex gap-1.5 text-xs">
              <span className="rounded-full bg-fg px-2.5 py-1 font-medium text-[#141414]">
                Yes, pay
              </span>
              <span className="rounded-full border border-white/18 px-2.5 py-1">Not now</span>
            </span>
          </div>
          <div className="flex max-w-[85%] flex-col self-end rounded-[14px_14px_4px_14px] bg-brand px-3 py-2.5 text-white">
            <span className="text-[11px] text-white/70">You · 8:03 PM</span>
            Yes please
          </div>
          <div className="flex max-w-[85%] flex-col self-start rounded-[14px_14px_14px_4px] bg-[#24262B] px-3 py-2.5">
            <span className="text-[11px] text-[#8F939A]">Stark · 8:04 PM</span>
            Done. Your token is 4821 0937 5512 8846 3019.
          </div>
        </div>
      </div>
    ),
  },
];

export function Safety() {
  const track = useRef<HTMLDivElement>(null);
  const [index, setIndex] = useState(0);

  function go(i: number) {
    const next = Math.max(0, Math.min(rules.length - 1, i));
    const el = track.current?.children[next] as HTMLElement | undefined;
    el?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "start" });
    setIndex(next);
  }

  return (
    <section id="safety" className="scroll-mt-16 bg-[#141414] text-fg">
      <div className="mx-auto flex max-w-[1240px] flex-col gap-12 px-4 py-24 sm:px-6 sm:py-[120px]">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div className="flex max-w-[620px] flex-col gap-3">
            <span className="text-xs tracking-[0.08em] text-brand-warm uppercase">Safety</span>
            <h2 className="m-0 font-serif text-[clamp(36px,3.8vw,52px)] leading-[1.05] font-normal tracking-[-0.015em]">
              What keeps your money safe
            </h2>
            <p className="m-0 text-[17px] text-[#B9BCC2]">
              Stark is careful by design. These four rules hold on every single payment.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="tabular text-[13px] text-[#B9BCC2]">
              {String(index + 1).padStart(2, "0")} / {String(rules.length).padStart(2, "0")}
            </span>
            <button
              type="button"
              aria-label="Previous rule"
              disabled={index === 0}
              onClick={() => go(index - 1)}
              className="flex size-11 cursor-pointer items-center justify-center rounded-full border border-white/20 bg-transparent text-fg disabled:opacity-40"
            >
              <Icons.ArrowLeft size={18} />
            </button>
            <button
              type="button"
              aria-label="Next rule"
              disabled={index === rules.length - 1}
              onClick={() => go(index + 1)}
              className="flex size-11 cursor-pointer items-center justify-center rounded-full border-0 bg-fg text-[#141414] disabled:opacity-40"
            >
              <Icons.ArrowRight size={18} />
            </button>
          </div>
        </div>

        <div
          ref={track}
          onScroll={(e) => {
            const el = e.currentTarget;
            const card = el.firstElementChild as HTMLElement | null;
            if (card) setIndex(Math.round(el.scrollLeft / (card.offsetWidth + 32)));
          }}
          className="-mx-4 flex snap-x snap-mandatory gap-8 overflow-x-auto scroll-px-4 px-4 [scrollbar-width:none] sm:mx-0 sm:scroll-px-0 sm:px-0"
        >
          {rules.map((rule, i) => (
            <article
              key={rule.title}
              className="flex min-w-0 flex-[0_0_88%] snap-start flex-col gap-3.5 md:flex-[0_0_calc((100%-32px)/2)]"
            >
              <span className="tabular text-sm text-[#8F939A]">
                {String(i + 1).padStart(2, "0")}
              </span>
              <h3 className="m-0 font-serif text-[clamp(28px,2.6vw,38px)] leading-[1.1] font-normal">
                {rule.title}
              </h3>
              <p className="m-0 max-w-[520px] text-base text-[#B9BCC2]">{rule.body}</p>
              <div
                className={`mt-6 flex h-[380px] items-center justify-center rounded-[22px] p-5 sm:h-[440px] sm:p-8 ${rule.bg}`}
              >
                {rule.demo}
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
