export function DefaultCatchBoundary() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[hsl(var(--background))] p-6">
      <div className="max-w-md space-y-3 rounded-3xl border border-border/60 bg-card p-8 shadow-xl">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
          Synapse UI
        </p>
        <h1 className="font-serif text-2xl text-foreground">Something went wrong.</h1>
        <p className="text-sm text-muted-foreground">
          The workbench hit an unexpected rendering error. Refresh the page and try again.
        </p>
      </div>
    </div>
  );
}
