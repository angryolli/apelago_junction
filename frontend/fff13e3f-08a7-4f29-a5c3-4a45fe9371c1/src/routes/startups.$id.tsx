import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import { ScoreTip } from "@/components/ScoreTip";
import { Shell, Score } from "@/components/Shell";
import { ApiError, createInquiry, getStartup, type Inquiry } from "@/lib/api";

export const Route = createFileRoute("/startups/$id")({
  loader: async ({ params }) => {
    try {
      return await getStartup(params.id);
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        throw notFound();
      }
      return null;
    }
  },
  head: ({ loaderData }) => ({
    meta: [
      { title: `${loaderData?.name ?? "Startup"} — Ocean Opportunity Radar` },
      { name: "description", content: loaderData?.tagline ?? "Startup assessment" },
      { property: "og:title", content: `${loaderData?.name ?? "Startup"} assessment` },
      { property: "og:description", content: loaderData?.tagline ?? "Startup assessment" },
      { property: "og:type", content: "article" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Detail,
});

const typeStyle: Record<string, string> = {
  Investor: "bg-primary text-primary-foreground",
  Grant: "bg-accent text-accent-foreground",
  Partner: "bg-secondary text-secondary-foreground",
  Client: "bg-primary-soft text-deep",
};

function InquiryList({ title, items, ordered = false }: { title: string; items: string[]; ordered?: boolean }) {
  const List = ordered ? "ol" : "ul";

  return (
    <div className="mt-5">
      <h3 className="text-sm font-semibold text-deep">{title}</h3>
      <List className={`mt-2 space-y-2 text-sm text-deep ${ordered ? "list-decimal pl-5" : "list-disc pl-5"}`}>
        {items.map((item) => <li key={item}>{item}</li>)}
      </List>
    </div>
  );
}

function Detail() {
  const { id } = Route.useParams();
  const loaded = Route.useLoaderData();
  const query = useQuery({
    queryKey: ["startup", id],
    queryFn: () => getStartup(id),
    staleTime: 30_000,
    ...(loaded ? { initialData: loaded } : {}),
  });
  const [shownFor, setShownFor] = useState(id);
  const [inquiry, setInquiry] = useState<Inquiry | null>(null);
  const [asking, setAsking] = useState(false);
  const [askError, setAskError] = useState("");
  if (shownFor !== id) {
    setShownFor(id);
    setInquiry(null);
    setAskError("");
  }
  const s = query.data;
  if (query.isPending) {
    return <Shell><Link to="/" className="text-sm text-primary">← Back</Link><p className="mt-6 text-muted-foreground">Loading assessment…</p></Shell>;
  }
  if (!s) {
    const missing = query.error instanceof ApiError && query.error.status === 404;
    return (
      <Shell>
        <Link to="/" className="text-sm text-primary">← Back</Link>
        <p className="mt-6 text-muted-foreground">
          {missing ? "Startup not found." : "This assessment could not be loaded. Check that the API is running."}
        </p>
      </Shell>
    );
  }
  const levels = [
    ["Ocean Impact Readiness", s.readiness.impact],
    ["Business Readiness (BRL)", s.readiness.business],
    ["Technology Readiness (TRL)", s.readiness.tech],
    ["Investment Readiness", s.readiness.investment],
  ] as const;
  const sourceLabels: Record<string, string> = {
    website: "Company website",
    dealroom: "Dealroom",
    blueinvest: "BlueInvest",
    business_finland: "Business Finland",
    prh: "PRH trade register",
    cordis: "CORDIS",
  };

  return (
    <Shell>
      <Link to="/" className="text-sm text-primary hover:underline">← Back to radar</Link>

      <div className="mt-4 flex flex-wrap items-center gap-6 rounded-2xl border bg-card p-8">
        {s.assessed ? <ScoreTip row={s}><Score value={s.thesisFit} size={96} /></ScoreTip> : <span className="grid h-24 w-24 place-items-center rounded-full border text-sm text-muted-foreground">Not scored</span>}
        <div className="flex-1">
          <p className="text-xs uppercase tracking-widest text-muted-foreground">{s.assessed ? "Thesis fit" : "Awaiting assessment"}</p>
          <h1 className="text-3xl font-semibold text-deep"><ScoreTip row={s}><span>{s.name}</span></ScoreTip></h1>
          <p className="text-muted-foreground">{s.tagline}</p>
          <p className="mt-2 text-sm text-muted-foreground">{s.sector} · {s.country} · {s.stage}{s.founded ? ` · founded ${s.founded}` : ""}{s.team ? ` · ${s.team} people` : ""} · raised {s.raised}</p>
          {s.aiThoughts && (
            <div className="mt-3 max-w-xl rounded-xl bg-primary-soft p-3 text-sm text-deep">
              <p className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">AI thoughts · predicted fit {s.predictedFit}</p>
              <p className="mt-1">{s.aiThoughts}</p>
            </div>
          )}
          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="button"
              disabled={asking}
              onClick={() => {
                setAsking(true);
                setAskError("");
                void createInquiry(s.id)
                  .then((result) => setInquiry(result))
                  .catch((error: unknown) => {
                    setAskError(error instanceof ApiError ? error.message : "The investor questions could not be written.");
                  })
                  .finally(() => setAsking(false));
              }}
              className="h-10 rounded-full bg-ocean px-5 text-sm font-medium text-primary-foreground disabled:opacity-60"
            >
              {asking ? "Writing questions…" : "Investor questions"}
            </button>
          </div>
          {askError && <p className="mt-3 text-sm text-destructive">{askError}</p>}
        </div>
      </div>

      {inquiry && (
        <section className="mt-6 rounded-2xl border bg-card p-6">
          <h2 className="font-semibold text-deep">Investor inquiry</h2>
          <InquiryList title="Questions to investigate" items={inquiry.questions} ordered />
          <InquiryList title="Outstanding risks" items={inquiry.risks} />
          <InquiryList title="Suggested introductions" items={inquiry.introductions} />
          <InquiryList title="Funding and partnership opportunities" items={inquiry.opportunities} />
        </section>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <section className="rounded-2xl border bg-card p-6 lg:col-span-1">
          <h2 className="mb-4 font-semibold text-deep">Readiness levels</h2>
          {!s.assessed && <p className="text-sm text-muted-foreground">Scores appear after source research is judged.</p>}
          <div className={`space-y-4 ${s.assessed ? "" : "mt-4 opacity-40"}`}>
            {levels.map(([l, v]) => (
              <div key={l}>
                <div className="mb-1 flex justify-between text-sm"><span>{l}</span><span className="font-semibold text-deep">{v}/9</span></div>
                <div className="flex gap-1">
                  {Array.from({ length: 9 }).map((_, i) => (
                    <div key={i} className={`h-2 flex-1 rounded-full ${i < v ? "bg-primary" : "bg-muted"}`} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-2xl border bg-card p-6 lg:col-span-2">
          <h2 className="mb-4 font-semibold text-deep">Investment potential</h2>
          {!s.assessed && <p className="mb-4 text-sm text-muted-foreground">These scores stay at zero until the evidence is judged.</p>}
          <div className={`grid gap-3 sm:grid-cols-2 ${s.assessed ? "" : "opacity-40"}`}>
            {s.dimensions.map((d) => (
              <div key={d.name}>
                <div className="mb-1 flex justify-between text-sm"><span>{d.name}</span><span className="text-muted-foreground">{d.score}/10</span></div>
                <div className="h-2 rounded-full bg-muted"><div className="h-2 rounded-full bg-ocean" style={{ width: `${d.score * 10}%` }} /></div>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-2xl border bg-card p-6">
          <h2 className="mb-3 font-semibold text-deep">Why it's promising</h2>
          <ul className="space-y-2 text-sm">{s.signals.map((x) => <li key={x} className="flex gap-2"><span className="text-primary">●</span>{x}</li>)}</ul>
          <h2 className="mb-3 mt-6 font-semibold text-deep">Risks</h2>
          <ul className="space-y-2 text-sm">{s.risks.map((x) => <li key={x} className="flex gap-2"><span className="text-warning">▲</span>{x}</li>)}</ul>
        </section>

        <section className="rounded-2xl border bg-card p-6 lg:col-span-2">
          <h2 className="mb-4 font-semibold text-deep">Prioritized opportunities</h2>
          <div className="space-y-3">
            {[...s.matches].sort((a, b) => b.fit - a.fit).map((m, i) => (
              <div key={m.name} className="flex items-center gap-4 rounded-xl bg-muted/60 p-3">
                <span className="w-5 font-display text-muted-foreground">{i + 1}</span>
                <span className={`w-20 rounded-full px-2 py-0.5 text-center text-xs ${typeStyle[m.type]}`}>{m.type}</span>
                <div className="flex-1">
                  <div className="font-medium text-deep">{m.name} <span className="text-xs text-muted-foreground">· {m.region}</span></div>
                  <div className="text-xs text-muted-foreground">{m.why}</div>
                </div>
                <span className="font-display font-semibold text-primary">{m.fit}%</span>
              </div>
            ))}
          </div>
        </section>
      </div>

      {(s.sources.length > 0 || s.judgeNotes) && (
        <section className="mt-6 rounded-2xl border bg-card p-6">
          <h2 className="font-semibold text-deep">Evidence from sources</h2>
          {s.judgeNotes && (
            <p className="mt-2 text-sm text-muted-foreground">
              {s.judgeVerdict ? `Judge: ${s.judgeVerdict}. ` : ""}{s.judgeNotes}
            </p>
          )}
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            {s.sources.map((source) => (
              <article key={source.source} className="rounded-xl border p-4">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="font-medium text-deep">{sourceLabels[source.source] ?? source.source}</h3>
                  <span className="text-xs text-muted-foreground">{source.found ? "Found" : "Not found"}</span>
                </div>
                <a href={source.url} target="_blank" rel="noreferrer" className="mt-1 block text-sm text-primary hover:underline">{source.title}</a>
                <p className="mt-2 max-h-24 overflow-hidden text-xs leading-5 text-muted-foreground">{source.excerpt}</p>
              </article>
            ))}
          </div>
        </section>
      )}

      <section className="mt-6 rounded-2xl bg-ocean p-8 text-primary-foreground shadow-soft">
        <h2 className="mb-4 text-xl font-semibold">Recommended next steps</h2>
        <ol className="grid gap-3 md:grid-cols-3">
          {s.nextSteps.map((n, i) => (
            <li key={n} className="rounded-xl bg-card/15 p-4 backdrop-blur"><div className="font-display text-2xl opacity-70">0{i + 1}</div>{n}</li>
          ))}
        </ol>
      </section>
    </Shell>
  );
}
