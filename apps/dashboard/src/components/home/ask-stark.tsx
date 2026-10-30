import { InputGroup, InputGroupAddon, InputGroupInput } from "@stark/ui/components/input-group";
import { useNavigate } from "@tanstack/react-router";
import { type SubmitEvent, useState } from "react";
import { AskSendButton } from "@/components/home/ask-send-button";
import { AskSpeakButton } from "@/components/home/ask-speak-button";

export function AskStark() {
  const navigate = useNavigate();
  const [text, setText] = useState("");

  const handleAskStark = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (text.trim()) navigate({ to: "/talk", search: { q: text.trim() } });
  };

  return (
    <form className="m-0" onSubmit={handleAskStark}>
      <InputGroup className="h-auto rounded-full border-white/10 bg-surface py-1.5 pr-1.5 pl-4.5 dark:bg-surface">
        <InputGroupInput
          aria-label="Ask Stark"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Ask Stark: “buy 2GB for my line”"
          className="h-auto px-0 py-2 text-[15px]"
        />
        <InputGroupAddon align="inline-end" className="py-0">
          {text.trim() ? <AskSendButton /> : <AskSpeakButton />}
        </InputGroupAddon>
      </InputGroup>
    </form>
  );
}
