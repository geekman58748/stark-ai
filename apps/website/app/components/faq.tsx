const questions = [
  {
    q: "Which bills can it pay?",
    a: "Prepaid electricity, airtime, data bundles and cable TV today, with internet and water next, wherever our bill-payment partner supports the provider. Every bill sits under the same spending limits.",
  },
  {
    q: "How does it know I’m running low?",
    a: "From your purchase history, and soon from a photo of your meter’s screen. It warns you a few days before you’d run out.",
  },
  {
    q: "What if it mishears me?",
    a: "It repeats the bill and the amount before paying, and anything outside your limits or your saved bills is refused anyway.",
  },
  {
    q: "Will it pay just because someone in the room says something?",
    a: "No. Voice notes only count when they include the word “Stark”, so everyday talk never triggers a payment.",
  },
  {
    q: "Who holds my money?",
    a: "You do. Stark can only pay the bills you added, inside limits only you can change. You can withdraw at any time.",
  },
];

export function Faq() {
  return (
    <section
      id="faq"
      className="mx-auto flex max-w-[760px] scroll-mt-20 flex-col gap-6 px-4 pb-28 sm:px-6 sm:pb-[140px]"
    >
      <h2 className="m-0 font-serif text-[clamp(30px,3vw,40px)] font-medium tracking-[-0.015em]">
        Questions
      </h2>
      <div className="flex flex-col">
        {questions.map(({ q, a }) => (
          <details key={q} className="group border-t border-[#E2E3DE] py-[18px] last:border-b">
            <summary className="flex cursor-pointer list-none justify-between gap-4 font-medium [&::-webkit-details-marker]:hidden">
              {q}
              <span aria-hidden="true" className="transition-transform group-open:rotate-45">
                +
              </span>
            </summary>
            <p className="mt-3 mb-0 text-ink-2">{a}</p>
          </details>
        ))}
      </div>
    </section>
  );
}
