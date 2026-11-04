import { type Story, StoryCard } from "~/components/story-card";
import { links } from "~/lib/links";

const stories: Story[] = [
  {
    who: "Prepaid light",
    ask: "Light just went. Top up the house 5k.",
    rule: "Inside your ₦10,000 one-go limit, so it pays and sends the 20-digit token back.",
  },
  {
    who: "Mum’s meter",
    ask: "Do Mum’s meter too, 10k.",
    rule: "Her meter is on your list, so it can. A meter you never added, it won’t touch.",
  },
  {
    who: "Match day",
    ask: "Renew DStv before the match.",
    rule: "Compact costs ₦7,900, the plan’s price. Nobody can talk it into a different figure.",
  },
  {
    who: "Your own line",
    ask: "Buy 2GB for my line.",
    rule: "Only your saved number. It never asks who to send airtime to.",
  },
  {
    who: "A big month",
    ask: "Pay 25k for light, the bill is heavy.",
    rule: "Over your limit, so it waits in the app for your yes. An hour, then it lapses.",
  },
  {
    who: "Travelling",
    ask: "I’m away this week. /pause",
    rule: "Every payment stops until you send /resume. It still answers questions.",
  },
  {
    who: "Before it runs out",
    ask: "Yes, top it up.",
    rule: "Stark warned first that the meter had about 4 days left, then waited for your yes.",
  },
  {
    who: "Keeping count",
    ask: "How much did I spend on light this month?",
    rule: "Answered from your receipts. A question never moves money.",
  },
];

export function Stories() {
  return (
    <section
      id="stories"
      className="mx-auto flex max-w-[1240px] scroll-mt-20 flex-col items-center gap-8 px-4 py-24 text-center sm:px-6 sm:py-[120px]"
    >
      <h2 className="m-0 font-serif text-[clamp(34px,3.6vw,48px)] leading-[1.05] font-normal tracking-[-0.015em]">
        What people ask it for
      </h2>
      <p className="m-0 max-w-[520px] text-[16px] text-ink-2">
        One sentence each, and the rule that decides what happens next.
      </p>
      <ul className="m-0 grid w-full list-none grid-cols-1 gap-4 p-0 sm:grid-cols-2 lg:grid-cols-4">
        {stories.map((story) => (
          <StoryCard key={story.who} story={story} />
        ))}
      </ul>
      <a
        href={links.demo}
        className="rounded-full bg-ink px-5 py-3 text-[14px] font-medium text-white no-underline"
      >
        Open a sample account
      </a>
    </section>
  );
}
