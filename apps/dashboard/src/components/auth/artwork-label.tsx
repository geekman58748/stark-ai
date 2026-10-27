export function ArtworkLabel() {
  return (
    <div className="absolute inset-x-0 top-0 z-10 p-4 lg:p-5">
      <span
        className="inline-flex items-center gap-2 rounded-full py-1.5 pr-3.5 pl-3"
        style={{ backgroundColor: "rgb(15 17 21 / 0.86)" }}
      >
        <span className="size-1.5 rounded-full bg-brand-warm" />
        <span className="text-[10px] font-medium tracking-[0.09em] text-white/90 uppercase">
          Prepaid power, handled
        </span>
      </span>
    </div>
  );
}
