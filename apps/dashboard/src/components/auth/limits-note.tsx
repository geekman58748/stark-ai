import { Icons } from "@stark/ui/components/icons";

export function LimitsNote() {
  return (
    <div className="mt-7 flex items-start gap-2.5 border-t border-line pt-6 text-[12.5px] leading-relaxed text-faint">
      <Icons.Lock size={14} className="mt-0.5 shrink-0" />
      <span>Stark can only pay the bills you add, inside limits only you can change.</span>
    </div>
  );
}
