import { Artwork } from "@/components/auth/artwork";
import { ArtworkLabel } from "@/components/auth/artwork-label";
import { ArtworkSeam } from "@/components/auth/artwork-seam";

export function ArtworkPanel() {
  return (
    <aside className="relative hidden min-h-dvh p-4 lg:flex lg:p-6">
      <div
        className="relative w-full overflow-hidden rounded-[20px]"
        style={{
          boxShadow: "0 24px 70px -28px rgb(0 0 0 / 0.85), 0 2px 10px rgb(0 0 0 / 0.45)",
        }}
      >
        <Artwork />
        <ArtworkLabel />
      </div>

      <ArtworkSeam />
    </aside>
  );
}
