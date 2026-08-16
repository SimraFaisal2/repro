import type { ReactNode } from "react";

export function Panel({
  title,
  right,
  children,
  className = "",
  bodyClass = "",
}: {
  title?: string;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClass?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      {title && (
        <header className="panel-head">
          <span>{title}</span>
          {right && <div className="flex items-center gap-2">{right}</div>}
        </header>
      )}
      <div className={bodyClass || "p-4"}>{children}</div>
    </section>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-xs text-muted">
      <span className="size-3 rounded-full border-2 border-border border-t-accent animate-spin" />
      {label}
    </span>
  );
}
