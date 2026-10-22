import type { Route } from "./+types/home";

export function meta(_: Route.MetaArgs) {
  return [{ title: "Stark" }];
}

export default function Home() {
  return (
    <main className="flex min-h-full flex-col items-center justify-center gap-2 p-8 text-center">
      <h1 className="text-2xl font-semibold">Stark dashboard</h1>
      <p className="text-muted">
        Screens and the routes behind them are in <code>docs/FRONTEND.md</code>.
      </p>
    </main>
  );
}
