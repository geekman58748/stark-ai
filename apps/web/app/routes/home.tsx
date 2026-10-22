import type { Route } from "./+types/home";

export function meta(_: Route.MetaArgs) {
  return [
    { title: "Stark AI — hellostark.xyz" },
    { name: "description", content: "Stark AI. Intelligence, deployed." },
    { property: "og:title", content: "Stark AI" },
    { property: "og:description", content: "Intelligence, deployed." },
    { property: "og:type", content: "website" },
  ];
}

export default function Home() {
  return (
    <div className="relative flex min-h-full flex-col items-center justify-center overflow-hidden p-8 text-center">
      <div
        aria-hidden
        className="pointer-events-none absolute -inset-[40%] bg-[radial-gradient(40rem_40rem_at_30%_20%,rgba(110,168,255,0.14),transparent_60%),radial-gradient(35rem_35rem_at_75%_80%,rgba(160,123,255,0.12),transparent_60%)]"
      />
      <main className="relative max-w-[40rem]">
        <span className="mb-[1.6rem] inline-block rounded-full border border-white/12 px-[0.9rem] py-[0.4rem] text-[0.8rem] tracking-[0.12em] text-muted uppercase">
          Stark AI
        </span>
        <h1 className="bg-[linear-gradient(120deg,var(--color-fg)_30%,var(--color-accent)_65%,var(--color-accent-2))] bg-clip-text text-[clamp(2.6rem,8vw,4.2rem)] leading-[1.05] font-bold tracking-[-0.03em] text-transparent">
          Intelligence, deployed.
        </h1>
        <p className="mt-[1.1rem] text-[clamp(1rem,2.5vw,1.25rem)] leading-[1.6] text-muted">
          Stark AI is on the way. Something sharp is coming to{" "}
          <strong>hellostark.xyz</strong>.
        </p>
        <a
          href="mailto:hello@hellostark.xyz"
          className="mt-[2.4rem] inline-block rounded-xl bg-[linear-gradient(120deg,var(--color-accent),var(--color-accent-2))] px-[1.8rem] py-[0.85rem] font-semibold text-bg no-underline transition-[transform,box-shadow] duration-150 ease-out hover:-translate-y-0.5 hover:shadow-[0_10px_30px_rgba(110,168,255,0.25)]"
        >
          Get in touch
        </a>
      </main>
      <footer className="absolute bottom-6 text-[0.85rem] text-muted">
        &copy; 2026 Stark AI ·{" "}
        <a href="https://hellostark.xyz" className="underline">
          hellostark.xyz
        </a>
      </footer>
    </div>
  );
}
