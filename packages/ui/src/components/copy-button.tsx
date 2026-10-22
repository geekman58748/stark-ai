import { Button } from "@stark/ui/components/button";
import { useState } from "react";

export function CopyButton({ value, label = "Copy" }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      variant="secondary"
      onClick={async () => {
        await navigator.clipboard?.writeText(value);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
    >
      {copied ? "Copied" : label}
    </Button>
  );
}
