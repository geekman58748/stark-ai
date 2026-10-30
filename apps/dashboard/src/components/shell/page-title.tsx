import type { ReactNode } from "react";

export function PageTitle({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <h1 className="m-0 font-serif text-[34px] leading-[1.1] font-medium tracking-[-0.01em]">
        {children}
      </h1>
      {aside ? <div className="ml-auto">{aside}</div> : null}
    </div>
  );
}
