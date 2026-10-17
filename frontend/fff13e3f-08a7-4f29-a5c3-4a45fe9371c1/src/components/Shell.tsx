import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";

export function Shell({ children, wide }: { children: ReactNode; wide?: boolean }) {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 border-b bg-card">
        <div className={`flex items-center px-6 py-3 ${wide ? "" : "mx-auto max-w-6xl"}`}>
          <Link to="/" className="flex items-center">
            <img
              src="/logo.png"
              alt="Ocean Opportunity Radar for A'Pelago × Redstone"
              className="h-16 w-auto"
            />
          </Link>
        </div>
      </header>
      <main className={`mx-auto px-6 py-10 ${wide ? "max-w-none" : "max-w-6xl"}`}>{children}</main>
    </div>
  );
}

export function Score({ value, size = 56, stroke = "stroke-primary" }: { value: number; size?: number; stroke?: string }) {
  const r = size / 2 - 5;
  const c = 2 * Math.PI * r;
  return (
    <svg width={size} height={size} className="shrink-0">
      <circle cx={size / 2} cy={size / 2} r={r} className="fill-none stroke-muted" strokeWidth={5} />
      <circle
        cx={size / 2} cy={size / 2} r={r}
        className={`fill-none ${stroke}`}
        strokeWidth={5} strokeLinecap="round"
        strokeDasharray={c} strokeDashoffset={c * (1 - value / 100)}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
      <text x="50%" y="50%" dominantBaseline="central" textAnchor="middle" className="fill-deep font-display text-sm font-semibold">
        {value}
      </text>
    </svg>
  );
}
