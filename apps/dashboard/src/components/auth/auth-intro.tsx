import { Eyebrow } from "@stark/ui/components/eyebrow";
import { Link } from "@tanstack/react-router";

export function AuthIntro({
  eyebrow,
  title,
  prompt,
  link,
}: {
  eyebrow: string;
  title: string;
  prompt: string;
  link: { to: "/login" | "/start"; label: string };
}) {
  return (
    <div className="mt-10 sm:mt-12">
      <Eyebrow>{eyebrow}</Eyebrow>
      <h1 className="m-0 mt-2 font-serif text-[34px] leading-[1.06] font-medium tracking-[-0.015em] text-fg sm:text-[42px]">
        {title}
        <span className="text-brand">.</span>
      </h1>
      <p className="m-0 mt-2.5 text-[14px] text-fg-2">
        {prompt}{" "}
        <Link to={link.to} className="font-medium text-brand no-underline hover:text-brand-warm">
          {link.label}
        </Link>
      </p>
    </div>
  );
}
