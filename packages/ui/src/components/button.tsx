import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";
import { cn } from "../utils/cn";

export const buttonVariants = cva(
  "inline-flex cursor-pointer items-center justify-center gap-1.5 rounded-full font-medium no-underline transition-colors disabled:cursor-not-allowed disabled:opacity-50",
  {
    variants: {
      variant: {
        primary: "bg-brand text-white hover:bg-[#d04a12]",
        secondary: "border border-white/8 bg-surface-2 text-fg hover:bg-surface-3",
        ghost: "bg-transparent text-fg-2 hover:text-fg",
        light: "bg-fg text-canvas-deep hover:bg-white",
        ink: "bg-ink text-white hover:bg-black",
        paper: "bg-paper-2 text-ink hover:bg-[#dedad0]",
      },
      size: {
        sm: "min-h-9 px-4 text-[13px]",
        md: "min-h-11 px-5 text-sm",
        lg: "min-h-12 px-5 text-[15px] font-semibold",
        icon: "size-10",
      },
      block: {
        true: "w-full",
      },
    },
    defaultVariants: { variant: "primary", size: "sm" },
  },
);

export type ButtonVariantProps = VariantProps<typeof buttonVariants>;

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & ButtonVariantProps;

/** For links that look like buttons, use `buttonVariants()` on the link's className. */
export function Button({
  className,
  variant,
  size,
  block,
  type = "button",
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(buttonVariants({ variant, size, block }), className)}
      {...props}
    />
  );
}
