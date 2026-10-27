import { TalkBrand } from "@/components/talk/talk-brand";
import { TalkCloseButton } from "@/components/talk/talk-close-button";

export function TalkHeader() {
  return (
    <header className="relative flex items-center justify-between">
      <TalkBrand />
      <TalkCloseButton />
    </header>
  );
}
