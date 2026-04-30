import { Link } from "@tanstack/react-router";

export function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[hsl(var(--background))] p-6">
      <div className="max-w-md space-y-4 rounded-3xl border border-border/60 bg-card p-8 shadow-xl">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
          NewBro UI
        </p>
        <h1 className="font-serif text-3xl text-foreground">Page not found.</h1>
        <p className="text-sm text-muted-foreground">
          This route does not exist in the current workbench build.
        </p>
        <Link
          to="/"
          className="inline-flex rounded-full bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
        >
          Return home
        </Link>
      </div>
    </div>
  );
}
