import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import { DemoTour, startupDemo } from "@/components/DemoTour";
import { ScoreTip } from "@/components/ScoreTip";
import { Shell, Score } from "@/components/Shell";
import { type PitchSummary } from "@/data/radar";
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

function judgePoints(notes: string): string[] {
  const parts = notes
    .split(/(?<=[.!?])\s+(?=[A-Z])/)
    .map((part) => part.trim())
    .filter(Boolean);

  return parts.length > 0 ? parts : [notes];
}

function verdictStyle(verdict: string): string {
  if (verdict === "supported") return "bg-primary-soft text-primary";
  if (verdict === "revised") return "bg-warning/15 text-deep";
  return "bg-muted text-muted-foreground";
}

function roleFor(text: string, name: string): string {
  const roleMatch = text.match(new RegExp(`${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}[^.]*?\\bas ([^.;,]{3,80})`, "i"));
  const titled = text.match(/,\s*([A-Za-z][A-Za-z &-]{1,32})\s*$/)?.[1].trim();
  const sentence = /\b(is|as|the|identifies|names)\b/i.test(text);
  const role = roleMatch?.[1].split(/\s+and\s+(?=(describes|says|identifies|names|does|notes)\b)/i)[0].trim()
    ?? titled
    ?? (/co-founder/i.test(text) ? "Co-founder" : /founder/i.test(text) || !sentence ? "Founder" : /\bCEO\b/.test(text) ? "CEO" : "Contact");
  return role.charAt(0).toUpperCase() + role.slice(1);
}

function contactPerson(founders: string): { name: string; role: string } | null {
  const text = founders.trim();
  if (!text) return null;
  const named = text.match(/(?:identifies|names) ((?:Dr\. )?[A-ZÀ-Ý][\p{L}'’-]+(?: [A-ZÀ-Ý][\p{L}'’-]+){0,3})/u)
    ?? text.match(/^((?:Dr\. )?[A-ZÀ-Ý][\p{L}'’-]+(?: [A-ZÀ-Ý][\p{L}'’-]+){0,3})/u);
  if (!named) return null;
  const name = named[1].trim();
  return { name, role: roleFor(text, name) };
}

function personMatchingEmail(founders: string, email: string): { name: string; role: string } | null {
  const local = email.split("@")[0]?.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase() ?? "";
  const names = founders.match(/(?:Dr\. )?[A-ZÀ-Ý][\p{L}'’-]+(?: [A-ZÀ-Ý][\p{L}'’-]+){1,3}/gu) ?? [];
  for (const raw of names) {
    const name = raw.replace(/^Dr\. /, "");
    const tokens = name.split(/\s+/).map((part) => part.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase());
    if (tokens.some((token) => token.length >= 3 && local.includes(token))) {
      return { name, role: roleFor(founders, name) };
    }
  }
  return null;
}

function initials(name: string): string {
  return name.split(/\s+/).filter((part) => part !== "Dr.").slice(0, 2).map((part) => part[0]).join("");
}

function websiteHref(website: string): string {
  if (!website) return "";
  return website.startsWith("http") ? website : `https://${website}`;
}

function recorded(value: string): boolean {
  const text = value.trim();
  return text !== "" && text !== "—" && text !== "-" && text !== "–";
}

function headerFacts(startup: { sector: string; country: string; stage: string; founded: number; raised: string; team: number }) {
  const stage = startup.stage.trim();
  const stageNote = recorded(stage) && (stage.length > 32 || /[;.]/.test(stage));
  const facts = [
    startup.sector,
    startup.country,
    stageNote ? "" : stage,
    startup.founded ? `Founded ${startup.founded}` : "",
    startup.team ? `${startup.team} people` : "",
    recorded(startup.raised) ? `Raised ${startup.raised}` : "",
  ].filter(recorded);
  return { facts, stageNote: stageNote ? stage : "" };
}

function PitchDeck({ startupId, pitch }: { startupId: string; pitch?: PitchSummary }) {
  if (!pitch?.filename && !pitch?.overview && !pitch?.gaps?.length) return null;
  const blocks = [
    ["Problem", pitch.problem],
    ["Solution", pitch.solution],
    ["Traction", pitch.traction],
    ["Team", pitch.team],
    ["The ask", pitch.ask],
  ].filter((entry): entry is [string, string] => Boolean(entry[1]));

  return (
    <section className="mt-6 rounded-2xl border bg-card p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-semibold text-deep">Pitch deck</h2>
        {pitch.filename && (
          <a href={`/api/startups/${encodeURIComponent(startupId)}/deck`} className="text-sm font-medium text-primary hover:underline">
            Download {pitch.filename}
          </a>
        )}
      </div>
      {pitch.overview && <p className="mt-3 max-w-3xl text-sm leading-relaxed text-deep">{pitch.overview}</p>}
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        {blocks.map(([title, text]) => (
          <div key={title}>
            <h3 className="text-sm font-semibold text-deep">{title}</h3>
            <p className="mt-1 text-sm leading-relaxed text-deep">{text}</p>
          </div>
        ))}
      </div>
      {(pitch.gaps?.length ?? 0) > 0 && (
        <ul className="mt-4 space-y-2 text-sm">
          {pitch.gaps.map((gap) => <li key={gap} className="flex gap-2"><span className="text-warning">▲</span>{gap}</li>)}
        </ul>
      )}
    </section>
  );
}

function ContactCard({ founders, website, email }: { founders: string; website: string; email: string }) {
  const person = (email ? personMatchingEmail(founders, email) : null) ?? contactPerson(founders);
  const href = websiteHref(website);
  const samePerson = founders.trim() === person?.name || founders.trim() === `${person?.name}, ${person?.role}`;
  const note = founders.trim() && !samePerson ? founders.trim() : "";

  return (
    <section data-tour="contact" className="mt-6 rounded-2xl border bg-card p-6">
      <p className="text-xs uppercase tracking-widest text-muted-foreground">Contact for further information</p>
      <div className="mt-4 flex items-start gap-4">
        <span className="grid h-14 w-14 shrink-0 place-items-center rounded-full bg-ocean text-sm font-semibold text-primary-foreground">
          {person ? initials(person.name) : "—"}
        </span>
        <div className="min-w-0">
          <h2 className="text-xl font-semibold text-deep">{person?.name ?? "No named contact"}</h2>
          <p className="text-sm text-muted-foreground">{person?.role ?? "The assessment does not name a person yet."}</p>
          {note && <p className="mt-3 max-w-2xl text-sm leading-relaxed text-deep">{note}</p>}
          {email ? (
            <a href={`mailto:${email}`} className="mt-3 block text-sm font-medium text-primary hover:underline">
              {email}
            </a>
          ) : (
            <p className="mt-3 text-sm text-muted-foreground">No published email</p>
          )}
          {href && (
            <a href={href} target="_blank" rel="noreferrer" className="mt-1 inline-block text-sm text-primary hover:underline">
              {website}
            </a>
          )}
        </div>
      </div>
    </section>
  );
}

function TenScale({ value }: { value: number }) {
  return (
    <div className="flex gap-1" aria-hidden="true">
      {Array.from({ length: 10 }, (_, index) => (
        <div key={index} className={`h-2 flex-1 rounded-full ${index < value ? "bg-primary" : "bg-muted"}`} />
      ))}
    </div>
  );
}

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
  const { facts, stageNote } = headerFacts(s);
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

      <div className="mt-4 flex flex-col gap-5 rounded-2xl border bg-card p-5 sm:flex-row sm:items-start sm:gap-6 sm:p-8">
        {s.assessed ? <ScoreTip row={s}><Score value={s.thesisFit} size={96} /></ScoreTip> : <span className="grid h-24 w-24 place-items-center rounded-full border text-sm text-muted-foreground">Not scored</span>}
        <div className="min-w-0 flex-1">
          <p className="text-xs uppercase tracking-widest text-muted-foreground">{s.assessed ? "Thesis fit" : "Awaiting assessment"}</p>
          <h1 className="text-3xl font-semibold text-deep"><ScoreTip row={s}><span>{s.name}</span></ScoreTip></h1>
          <p className="max-w-2xl leading-relaxed text-muted-foreground">{s.tagline}</p>
          {(facts.length > 0 || stageNote) && (
            <div className="mt-3 space-y-2">
              {facts.length > 0 && (
                <ul className="flex flex-wrap gap-2">
                  {facts.map((fact) => (
                    <li key={fact} className="rounded-xl bg-secondary px-3 py-1 text-sm leading-5 text-muted-foreground">{fact}</li>
                  ))}
                </ul>
              )}
              {stageNote && <p className="max-w-2xl text-sm leading-6 text-deep">{stageNote}</p>}
            </div>
          )}
          {s.aiThoughts && (
            <div className="mt-3 max-w-2xl rounded-xl bg-primary-soft p-4 text-sm text-deep">
              <p className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">AI thoughts · predicted fit {s.predictedFit}</p>
              <p className="mt-2 leading-6">{s.aiThoughts}</p>
            </div>
          )}
          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="button"
              data-tour="questions"
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

      <ContactCard founders={s.profile.founders} website={s.profile.website} email={s.profile.email} />
      <PitchDeck startupId={s.id} pitch={s.pitch} />

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
                <div className="mb-1 flex justify-between text-sm"><span>{l}</span><span className="font-semibold text-deep">{v}/10</span></div>
                <TenScale value={v} />
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
                <TenScale value={d.score} />
              </div>
            ))}
          </div>
        </section>

        <section className="grid gap-8 rounded-2xl border bg-card p-6 lg:col-span-3 lg:grid-cols-2">
          <div>
            <h2 className="mb-3 font-semibold text-deep">Why it's promising</h2>
            <ul className="space-y-2 text-sm">{s.signals.map((x) => <li key={x} className="flex gap-2"><span className="text-primary">●</span>{x}</li>)}</ul>
          </div>
          <div>
            <h2 className="mb-3 font-semibold text-deep">Risks</h2>
            <ul className="space-y-2 text-sm">{s.risks.map((x) => <li key={x} className="flex gap-2"><span className="text-warning">▲</span>{x}</li>)}</ul>
          </div>
        </section>
      </div>

      {(s.sources.length > 0 || s.judgeNotes) && (
        <section className="mt-6 rounded-2xl border bg-card p-6">
          <h2 className="font-semibold text-deep">Evidence from sources</h2>
          {s.judgeNotes && (
            <div className="mt-4 rounded-xl bg-secondary/70 p-4">
              <div className="flex items-center gap-2">
                <p className="text-xs uppercase tracking-widest text-muted-foreground">Judge</p>
                {s.judgeVerdict && (
                  <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${verdictStyle(s.judgeVerdict)}`}>
                    {s.judgeVerdict}
                  </span>
                )}
              </div>
              <ul className="mt-3 space-y-2 text-sm leading-relaxed text-deep">
                {judgePoints(s.judgeNotes).map((point) => (
                  <li key={point} className="flex gap-2">
                    <span className="mt-1 text-primary">●</span>
                    <span>{point}</span>
                  </li>
                ))}
              </ul>
            </div>
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

      <DemoTour steps={startupDemo} ready />
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
