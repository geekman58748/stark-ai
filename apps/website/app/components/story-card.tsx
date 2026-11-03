export type Story = { who: string; ask: string; rule: string };

export function StoryCard({ story }: { story: Story }) {
  return (
    <li className="flex flex-col gap-3 rounded-[18px] bg-white p-5 text-left shadow-[0_20px_50px_rgba(15,17,21,0.06),0_1px_0_rgba(15,17,21,0.04)]">
      <span className="text-[12px] font-medium tracking-[0.04em] text-ink-3 uppercase">
        {story.who}
      </span>
      <p className="m-0 font-serif text-[20px] leading-[1.3] tracking-[-0.01em]">“{story.ask}”</p>
      <p className="m-0 mt-auto text-[14px] leading-[1.45] text-ink-2">{story.rule}</p>
    </li>
  );
}
