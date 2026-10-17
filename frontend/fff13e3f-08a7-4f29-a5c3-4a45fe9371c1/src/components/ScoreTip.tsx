import { useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import type { Row } from "@/data/radar";

export function ScoreTip({ row, children }: { row: Row; children: ReactNode }) {
  const [place, setPlace] = useState<{ top: number; left: number } | null>(null);
  if (!row.assessed) return <>{children}</>;

  return (
    <span
      className="inline-flex"
      onMouseEnter={(event) => {
        const rect = event.currentTarget.getBoundingClientRect();
        setPlace({
          top: rect.bottom,
          left: Math.min(rect.left, window.innerWidth - 360),
        });
      }}
      onMouseLeave={() => setPlace(null)}
    >
      {children}
      {place && createPortal(
        <span
          className="pointer-events-none fixed z-50 w-[22rem] rounded-xl border bg-card p-3 text-left text-xs font-semibold leading-5 text-deep shadow-soft"
          style={{ top: place.top + 6, left: Math.max(12, place.left) }}
        >
          {twoSentences(lead(row))}
        </span>,
        document.body,
      )}
    </span>
  );
}

function twoSentences(text: string): string {
  const sentences = text.match(/[^.!?]+[.!?]+/g) ?? [text];

  return sentences.slice(0, 2).join(" ").trim();
}

function lead(row: Row): string {
  if (row.scoreExplanation) return row.scoreExplanation;

  const strong = [...row.dimensions].filter((item) => item.score >= 6).sort((a, b) => b.score - a.score).slice(0, 3);
  const because = strong.length
    ? joinPhrase(strong.map((item) => `${item.name.toLowerCase()} (${item.score}/10)`))
    : "the recorded evidence is still thin";
  const limit = row.risks[0] || "Commercial and financial evidence is still limited.";

  return `${row.name} scores ${row.thesisFit}/100 because ${because} carry the most weight. ${limit}`;
}

function joinPhrase(items: string[]): string {
  if (items.length <= 1) return items[0] ?? "";
  if (items.length === 2) return `${items[0]} and ${items[1]}`;

  return `${items.slice(0, -1).join(", ")}, and ${items[items.length - 1]}`;
}
