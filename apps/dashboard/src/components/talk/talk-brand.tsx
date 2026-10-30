import { LogoMark } from "@stark/ui/components/logo";

export function TalkBrand() {
  return (
    <span className="flex items-center gap-2">
      <LogoMark cutout="#111211" />
      <span className="font-serif text-[19px] font-semibold tracking-[-0.02em]">Stark</span>
    </span>
  );
}
