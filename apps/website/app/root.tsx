import {
  isRouteErrorResponse,
  Links,
  Meta,
  Outlet,
  Scripts,
  ScrollRestoration,
} from "react-router";

import type { Route } from "./+types/root";
import "./app.css";

export const links: Route.LinksFunction = () => [
  {
    rel: "icon",
    href: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='%23C2410C' d='M12 1.5c-4.6 0-8.3 3.3-8.3 7.9V15c0 1.5.7 2.9 1.8 3.8L9 22h6l3.5-3.2A4.9 4.9 0 0020.3 15V9.4c0-4.6-3.7-7.9-8.3-7.9z'/%3E%3C/svg%3E",
  },
];

export function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta name="theme-color" content="#F4F2EC" />
        <Meta />
        <Links />
      </head>
      <body>
        {children}
        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  );
}

export default function App() {
  return <Outlet />;
}

export function ErrorBoundary({ error }: Route.ErrorBoundaryProps) {
  const notFound = isRouteErrorResponse(error) && error.status === 404;

  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-4 p-8 text-center">
      <h1 className="m-0 font-serif text-5xl font-medium">
        {notFound ? "Nothing here" : "Something went wrong"}
      </h1>
      <p className="m-0 text-ink-2">
        {notFound ? "That page doesn’t exist." : "Please try again in a moment."}
      </p>
      <a href="/" className="text-ink">
        Back to Stark
      </a>
    </main>
  );
}
