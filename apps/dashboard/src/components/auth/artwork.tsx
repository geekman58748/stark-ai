import { useEffect, useState } from "react";

const ARTWORK = "/godhand.mp4";
const STILL = "/godhand-poster.jpg";

export function Artwork() {
  const [still, setStill] = useState(false);

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => setStill(query.matches);
    sync();
    query.addEventListener("change", sync);
    return () => query.removeEventListener("change", sync);
  }, []);

  const frame = "absolute inset-0 block h-full w-full object-cover";

  return still ? (
    <img src={STILL} alt="" aria-hidden="true" className={frame} />
  ) : (
    <video
      src={ARTWORK}
      poster={STILL}
      autoPlay
      muted
      loop
      playsInline
      preload="auto"
      aria-hidden="true"
      tabIndex={-1}
      className={frame}
    />
  );
}
