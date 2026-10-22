import { Closing } from "~/components/closing";
import { Faq } from "~/components/faq";
import { Funding } from "~/components/funding";
import { Hero, Intro } from "~/components/hero";
import { Safety } from "~/components/safety";
import { SiteHeader } from "~/components/site-header";
import { Statement } from "~/components/statement";
import { WaysToAsk } from "~/components/ways-to-ask";
import type { Route } from "./+types/home";

const title = "Stark · The agent that pays your bills by voice";
const description =
  "Send a voice note and Stark pays your electricity, airtime, data and TV, inside limits you set.";

export function meta(_: Route.MetaArgs) {
  return [
    { title },
    { name: "description", content: description },
    { property: "og:title", content: title },
    { property: "og:description", content: description },
    { property: "og:type", content: "website" },
    { property: "og:url", content: "https://hellostark.xyz" },
  ];
}

export default function Home() {
  return (
    <div className="overflow-x-clip">
      <SiteHeader />
      <main>
        <Hero />
        <Intro />
        <Statement />
        <WaysToAsk />
        <Safety />
        <Funding />
        <Faq />
      </main>
      <Closing />
    </div>
  );
}
