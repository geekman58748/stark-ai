import type { CSSProperties } from "react";

const EQ_BARS = Array.from(
  { length: 12 },
  (_, i) =>
    ({
      "--i": `${(i % 6) * 60}ms`,
      "--d": `${600 + ((i * 137) % 460)}ms`,
    }) as CSSProperties,
);

export function VoiceEq() {
  return (
    <div className="voice-eq" aria-hidden="true">
      {EQ_BARS.map((style, i) => (
        <i key={i} style={style} />
      ))}
    </div>
  );
}
