import { useEffect, useState } from "react";

const STORAGE_KEY = "ocean-radar-demo";

export type DemoStep = {
  id: string;
  target: string;
  title: string;
  body: string;
  nextLabel?: string;
};

export const homeDemo: DemoStep[] = [
  {
    id: "filters",
    target: "filters",
    title: "Startup overview and filtering",
    body: "The table ranks companies by thesis fit. Search by name, choose a sector, or use Columns to decide which facts stay on screen.",
  },
  {
    id: "grades",
    target: "grades",
    title: "Hover a grade",
    body: "The turquoise ring is the current thesis fit. The dark ring is the predicted fit if the company continues only on the evidence already in hand. Hover either ring for the short explanation.",
  },
  {
    id: "compare",
    target: "compare",
    title: "Compare two firms",
    body: "Tick two to four companies, then press Compare. You get the scores side by side and a short note on which one fits the thesis you pick.",
  },
  {
    id: "deck",
    target: "deck",
    title: "Add a pitch deck",
    body: "Add startup takes a website and an optional pitch deck. The slides are summarised into the problem, solution, traction, team, and ask. The dialog also has an example deck.",
  },
  {
    id: "open",
    target: "open",
    title: "Open a startup",
    body: "Press a company name for the full assessment: readiness, risks, evidence, and the next steps worth taking.",
    nextLabel: "Open a startup",
  },
];

export const startupDemo: DemoStep[] = [
  {
    id: "questions",
    target: "questions",
    title: "Investor questions",
    body: "This writes five things to confirm, plus risks, introductions, and funding or partnership ideas. Use it when you want that list.",
  },
  {
    id: "contact",
    target: "contact",
    title: "Contact the person",
    body: "The card names the person on record. When the company site publishes an email, press it to write to them.",
    nextLabel: "Done",
  },
];

const order = [...homeDemo, ...startupDemo];

export function markStartupDemo() {
  const value = localStorage.getItem(STORAGE_KEY);
  if (!value || value === "done" || value === "questions" || value === "contact") return;
  localStorage.setItem(STORAGE_KEY, "questions");
}

function readStep(): string | null {
  const value = localStorage.getItem(STORAGE_KEY);
  if (!value || value === "done") return null;
  return order.some((step) => step.id === value) ? value : null;
}

function writeStep(id: string) {
  localStorage.setItem(STORAGE_KEY, id);
}

function finishDemo() {
  localStorage.setItem(STORAGE_KEY, "done");
}

export function DemoTour({
  steps,
  ready,
  onAdvance,
}: {
  steps: DemoStep[];
  ready: boolean;
  onAdvance?: () => void;
}) {
  const [stepId, setStepId] = useState<string | null>(null);
  const [box, setBox] = useState<{ top: number; left: number; width: number; height: number } | null>(null);
  const step = steps.find((item) => item.id === stepId) ?? null;
  const index = step ? order.findIndex((item) => item.id === step.id) : -1;

  useEffect(() => {
    if (!ready) return;
    const current = readStep();
    if (current && steps.some((item) => item.id === current)) {
      setStepId(current);
      return;
    }
    if (current === null && localStorage.getItem(STORAGE_KEY) !== "done" && steps[0]?.id === "filters") {
      writeStep("filters");
      setStepId("filters");
      return;
    }
    setStepId(null);
  }, [ready, steps]);

  useEffect(() => {
    if (!step) return;
    const target = () => document.querySelector(`[data-tour="${step.target}"]`) as HTMLElement | null;
    const place = () => {
      if (step.id === "compare") {
        const ticks = [...document.querySelectorAll('input[aria-label^="Compare"]')].slice(0, 4);
        if (ticks.length === 0) {
          setBox(null);
          return;
        }
        const rects = ticks.map((node) => node.getBoundingClientRect());
        const top = Math.min(...rects.map((rect) => rect.top));
        const left = Math.min(...rects.map((rect) => rect.left));
        const right = Math.max(...rects.map((rect) => rect.right));
        const bottom = Math.max(...rects.map((rect) => rect.bottom));
        setBox({ top, left, width: right - left, height: bottom - top });
        return;
      }
      const node = target();
      if (!node) {
        setBox(null);
        return;
      }
      const rect = node.getBoundingClientRect();
      setBox({ top: rect.top, left: rect.left, width: rect.width, height: rect.height });
    };
    const holdScroll = step.id === "grades";
    let scroller: HTMLElement | null = null;
    if (holdScroll || step.id === "compare") {
      const node = target();
      scroller = node?.closest(".overflow-auto") ?? null;
      if (node && scroller) {
        const header = scroller.querySelector("thead")?.getBoundingClientRect().height ?? 0;
        scroller.scrollTop += node.getBoundingClientRect().top - scroller.getBoundingClientRect().top - header - 16;
        scroller.scrollLeft = 0;
      }
    } else {
      target()?.scrollIntoView({ block: "center", inline: "nearest" });
    }
    place();
    const blockScroll = (event: Event) => event.preventDefault();
    const blockKeys = (event: KeyboardEvent) => {
      if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", " ", "PageUp", "PageDown", "Home", "End"].includes(event.key)) {
        event.preventDefault();
      }
    };
    const previousOverflow = scroller?.style.overflow ?? "";
    if (holdScroll && scroller) scroller.style.overflow = "hidden";
    if (holdScroll) {
      window.addEventListener("wheel", blockScroll, { capture: true, passive: false });
      window.addEventListener("touchmove", blockScroll, { capture: true, passive: false });
      window.addEventListener("keydown", blockKeys, true);
    }
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      if (scroller) scroller.style.overflow = previousOverflow;
      window.removeEventListener("wheel", blockScroll, true);
      window.removeEventListener("touchmove", blockScroll, true);
      window.removeEventListener("keydown", blockKeys, true);
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [step]);

  if (!step) return null;

  function skip() {
    finishDemo();
    setStepId(null);
  }

  function back() {
    const previous = order[index - 1];
    if (!previous || !steps.some((item) => item.id === previous.id)) return;
    writeStep(previous.id);
    setStepId(previous.id);
  }

  function next() {
    const following = order[index + 1];
    if (!following) {
      finishDemo();
      setStepId(null);
      return;
    }
    writeStep(following.id);
    if (steps.some((item) => item.id === following.id)) {
      setStepId(following.id);
      return;
    }
    setStepId(null);
    onAdvance?.();
  }

  const cardTop = step.id === "compare"
    ? Math.max(16, window.innerHeight - 230)
    : box ? Math.min(box.top + box.height + 12, window.innerHeight - 220) : 24;
  const cardLeft = step.id === "compare"
    ? Math.max(16, window.innerWidth - 380)
    : box ? Math.min(Math.max(16, box.left), window.innerWidth - 360) : 16;

  return (
    <div className="pointer-events-none fixed inset-0 z-50">
      {box ? (
        <div
          className="absolute rounded-2xl ring-2 ring-primary"
          style={{
            top: box.top - 6,
            left: box.left - 6,
            width: box.width + 12,
            height: box.height + 12,
            boxShadow: "0 0 0 9999px color-mix(in oklab, var(--color-deep) 45%, transparent)",
          }}
        />
      ) : (
        <div className="absolute inset-0 bg-deep/40" />
      )}
      <div
        className="pointer-events-auto absolute w-[22rem] max-w-[calc(100vw-2rem)] rounded-2xl border bg-card p-5 shadow-soft"
        style={{ top: Math.max(16, cardTop), left: cardLeft }}
      >
        <p className="text-xs uppercase tracking-widest text-muted-foreground">Demo · {index + 1} of {order.length}</p>
        <h2 className="mt-1 text-lg font-semibold text-deep">{step.title}</h2>
        <p className="mt-2 text-sm leading-relaxed text-deep">{step.body}</p>
        <div className="mt-4 flex items-center justify-between gap-3">
          <button type="button" onClick={skip} className="text-sm text-muted-foreground hover:text-deep">Skip</button>
          <div className="flex gap-2">
            {index > 0 && steps.some((item) => item.id === order[index - 1]?.id) && (
              <button type="button" onClick={back} className="rounded-full bg-secondary px-4 py-2 text-sm text-secondary-foreground">Back</button>
            )}
            <button type="button" onClick={next} className="rounded-full bg-ocean px-4 py-2 text-sm font-medium text-primary-foreground">
              {step.nextLabel ?? "Next"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
