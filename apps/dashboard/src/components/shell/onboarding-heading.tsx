export function OnboardingHeading({ title, lead }: { title: string; lead: string }) {
  return (
    <div className="flex flex-col gap-2">
      <h1 className="m-0 font-serif text-[34px] leading-[1.1] font-medium tracking-[-0.01em]">
        {title}
      </h1>
      <p className="m-0 text-[15px] text-fg-2">{lead}</p>
    </div>
  );
}
