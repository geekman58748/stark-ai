import { cn } from "@stark/ui/utils/cn";

type LogoMarkProps = {
  size?: number;
  /** The helmet's eye cut-outs take the background colour they sit on. */
  cutout?: string;
  className?: string;
};

/** Stark's helmet mark (an original design). */
export function LogoMark({ size = 26, cutout = "#111214", className }: LogoMarkProps) {
  return (
    <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" className={className}>
      <path
        fill="#C2410C"
        d="M12 1.5c-4.6 0-8.3 3.3-8.3 7.9V15c0 1.5.7 2.9 1.8 3.8L9 22h6l3.5-3.2A4.9 4.9 0 0020.3 15V9.4c0-4.6-3.7-7.9-8.3-7.9z"
      />
      <path
        fill={cutout}
        d="M6.6 10.2l4 .9v1.5l-4-.6zM17.4 10.2l-4 .9v1.5l4-.6zM10 17.2h4v1h-4zM11.4 3.2h1.2v4h-1.2z"
      />
    </svg>
  );
}

export function Logo({
  className,
  cutout,
  size,
}: {
  className?: string;
  cutout?: string;
  size?: number;
}) {
  return (
    <span className={cn("inline-flex items-center gap-2 font-semibold", className)}>
      <LogoMark cutout={cutout} size={size} />
      <span>Stark</span>
    </span>
  );
}
