import { LogoMark } from "@stark/ui/logo";

const bills = ["Electricity", "Airtime", "Data", "Cable TV", "Internet", "Water"];

const lines = [
  "Stark watches what you buy, warns you before you run out, and tops up when you say so.",
  "Light, airtime, data, TV. One agent for all of them.",
  "Talk the way you already do. Nothing new to learn.",
  "Just a voice note, and it’s done.",
];

export function Statement() {
  return (
    <section
      id="bills"
      className="mx-auto flex max-w-[640px] scroll-mt-20 flex-col gap-9 px-4 pb-28 sm:px-6 sm:pb-[140px]"
    >
      <p className="m-0 font-serif text-[clamp(24px,2.6vw,32px)] leading-[1.3] tracking-[-0.02em]">
        Stark is a bill agent that lives in your Telegram and on a phone by your meter, and pays
        every recurring bill the way a careful friend would.
      </p>
      <ul
        aria-label="Bills Stark pays"
        className="m-0 flex list-none flex-wrap gap-2 p-0 text-[13px]"
      >
        {bills.map((b, i) => (
          <li
            key={b}
            className={
              i === 0
                ? "rounded-full bg-ink px-3.5 py-[7px] font-medium text-white"
                : "rounded-full border border-rule px-3.5 py-[7px]"
            }
          >
            {b}
          </li>
        ))}
      </ul>
      <div className="flex max-w-[440px] items-center gap-3 rounded-[18px] bg-white px-4 py-3.5 shadow-[0_20px_50px_rgba(15,17,21,0.08),0_1px_0_rgba(15,17,21,0.04)]">
        <span className="flex size-9 flex-none items-center justify-center rounded-[10px] bg-ink">
          <LogoMark size={20} cutout="#0F1115" />
        </span>
        <span className="flex min-w-0 flex-1 flex-col text-[13px] leading-[1.35]">
          <strong className="font-semibold">Stark</strong>
          <span className="text-ink-2">
            Home meter is running low, about 4 days left. Top up ₦5,000?
          </span>
        </span>
        <span className="self-start text-[11px] text-ink-3">now</span>
      </div>
      <div className="flex flex-col gap-7 font-serif text-[clamp(20px,2vw,24px)] leading-[1.3] tracking-[-0.015em]">
        <p className="m-0">Never find out at 11pm that the meter is on zero.</p>
        {lines.map((l) => (
          <p key={l} className="m-0 text-ink-3">
            {l}
          </p>
        ))}
      </div>
    </section>
  );
}
