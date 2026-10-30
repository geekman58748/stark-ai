import { Button } from "@stark/ui/components/button";
import { Link, useNavigate } from "@tanstack/react-router";

export function CallbackError({ error }: { error: string }) {
  const navigate = useNavigate();
  return (
    <>
      <p role="alert" className="m-0 mt-2.5 text-[14px] leading-relaxed text-fg-2">
        {error}
      </p>
      <Button
        type="button"
        variant="brand"
        size="lg"
        block
        className="mt-6 h-12 text-[15px] font-semibold"
        onClick={() => navigate({ to: "/start" })}
      >
        Start again
      </Button>
      <p className="m-0 mt-3 text-[13px] text-faint">
        Or{" "}
        <Link to="/login" className="font-medium text-brand no-underline hover:text-brand-warm">
          log in with your email
        </Link>
        .
      </p>
    </>
  );
}
