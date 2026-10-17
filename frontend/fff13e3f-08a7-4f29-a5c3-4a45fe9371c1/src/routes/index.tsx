import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { ScoreTip } from "@/components/ScoreTip";
import { Shell, Score } from "@/components/Shell";
import { emptyProfile, type Profile, type Row } from "@/data/radar";
import { createStartup, createStartupFromLink, listSectors, listStartups } from "@/lib/api";
import { useResearch } from "@/lib/use-research";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Ocean Opportunity Radar — VC Scouting" },
      { name: "description", content: "Scout, score and match blue economy startups with investors, grants and partners." },
      { property: "og:title", content: "Ocean Opportunity Radar — VC Scouting" },
      { property: "og:description", content: "Decision-ready venture intelligence for funds and accelerators." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

const cols: { key: string; label: string; w: string; get: (r: Row) => React.ReactNode }[] = [
  { key: "readiness", label: "Readiness 1–9", w: "w-40", get: (r) => r.assessed ? (
    <div className="space-y-0.5 whitespace-nowrap">
      <div>Ocean {r.readiness.impact}</div>
      <div>Business {r.readiness.business}</div>
      <div>Tech {r.readiness.tech}</div>
      <div>Investment {r.readiness.investment}</div>
    </div>
  ) : "Not assessed" },
  { key: "match", label: "Top match", w: "w-52", get: (r) => {
    const top = [...r.matches].sort((a, b) => b.fit - a.fit)[0];
    if (!top) return "";
    return <div><div className="font-medium text-deep">{top.name}</div><div className="text-muted-foreground">{top.type} · {top.fit}%</div></div>;
  } },
  { key: "basics", label: "Company basics", w: "w-56", get: (r) => (
    <div className="space-y-0.5"><div>{r.profile.website}</div><div>{r.profile.hq}</div><div>{r.founded ? `Founded ${r.founded}` : "Founded —"}</div><div className="text-muted-foreground">{r.profile.founders}</div></div>
  ) },
  { key: "desc", label: "One-line description", w: "w-60", get: (r) => r.profile.description },
  { key: "kw", label: "Industry / keywords", w: "w-44", get: (r) => (
    <div className="flex flex-wrap gap-1">{r.profile.keywords.map((k) => <span key={k} className="rounded-md bg-primary-soft px-2 py-0.5 text-deep">{k}</span>)}</div>
  ) },
  { key: "problem", label: "Problem", w: "w-60", get: (r) => r.profile.problem },
  { key: "solution", label: "Solution / product", w: "w-60", get: (r) => r.profile.solution },
  { key: "bm", label: "Business model", w: "w-48", get: (r) => r.profile.businessModel },
  { key: "cust", label: "Target customers", w: "w-48", get: (r) => r.profile.customers },
  { key: "traction", label: "Traction", w: "w-52", get: (r) => r.profile.traction },
  { key: "funding", label: "Funding history", w: "w-56", get: (r) => r.profile.funding },
  { key: "adv", label: "Competitive advantage", w: "w-56", get: (r) => r.profile.advantage },
  { key: "comp", label: "Competitors", w: "w-60", get: (r) => r.profile.competitors },
  { key: "thesis", label: "Investment thesis / risks", w: "w-64", get: (r) => r.profile.thesis },
];

const compareLimit = 4;

function Index() {
  const [q, setQ] = useState("");
  const [sector, setSector] = useState("");
  const [open, setOpen] = useState(false);
  const [linkOpen, setLinkOpen] = useState(false);
  const [thoughtsId, setThoughtsId] = useState<string | null>(null);
  const [picked, setPicked] = useState<string[]>([]);
  const navigate = useNavigate();
  const research = useResearch();
  const startupsQuery = useQuery({
    queryKey: ["startups", q, sector],
    queryFn: () => listStartups({ q, sector }),
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });
  const sectorsQuery = useQuery({
    queryKey: ["sectors"],
    queryFn: listSectors,
    staleTime: 30_000,
  });
  const rows = startupsQuery.data ?? [];
  const list = useMemo(() => [...rows].sort((a, b) => b.thesisFit - a.thesisFit), [rows]);

  function togglePick(id: string) {
    setPicked((current) => {
      if (current.includes(id)) return current.filter((item) => item !== id);
      if (current.length >= compareLimit) return current;
      return [...current, id];
    });
  }

  return (
    <Shell wide>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold text-deep">Startup review</h1>
          <p className="text-sm text-muted-foreground">{list.length} {list.length === 1 ? "startup" : "startups"} · ranked by thesis fit · click a name to open the full assessment</p>
        </div>
        <div className="flex flex-wrap gap-3">
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by name…" aria-label="Search by name"
            className="h-10 w-64 rounded-full border bg-card px-4 text-sm outline-none focus:ring-2 focus:ring-ring" />
          <select value={sector} onChange={(e) => setSector(e.target.value)} aria-label="Filter by sector"
            className="h-10 rounded-full border bg-card px-4 text-sm outline-none focus:ring-2 focus:ring-ring">
            <option value="">All sectors</option>
            {(sectorsQuery.data ?? []).map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <button onClick={() => setLinkOpen(true)} className="h-10 rounded-full border bg-card px-5 text-sm font-medium text-deep hover:bg-muted">
            Add from link
          </button>
          <button onClick={() => setOpen(true)} className="h-10 rounded-full bg-ocean px-5 text-sm font-medium text-primary-foreground shadow-soft hover:opacity-90">
            + Add startup
          </button>
        </div>
      </div>

      {research.status && research.status.status !== "idle" && (
        <p className="mb-4 text-sm text-muted-foreground">
          {research.status.message}
          {research.status.errors.length > 0 ? ` ${research.status.errors.join(" ")}` : ""}
        </p>
      )}

      {startupsQuery.isError && (
        <p className="mb-4 text-sm text-destructive">The startup list could not be loaded. Check that the API is running.</p>
      )}

      {picked.length > 0 && (
        <div className="mb-4 flex flex-wrap items-center gap-3 rounded-2xl border bg-card px-4 py-3">
          <p className="text-sm text-deep">{picked.length} selected · choose 2 to 4</p>
          <button
            type="button"
            disabled={picked.length < 2}
            onClick={() => void navigate({ to: "/compare", search: { ids: picked.join(",") } })}
            className="h-9 rounded-full bg-ocean px-4 text-sm font-medium text-primary-foreground disabled:opacity-50"
          >
            Compare
          </button>
          <button type="button" onClick={() => setPicked([])} className="text-sm text-muted-foreground hover:text-deep">
            Clear
          </button>
        </div>
      )}

      <div className="overflow-auto rounded-2xl border bg-card" style={{ maxHeight: "75vh" }}>
        <table className="border-separate border-spacing-0 text-xs">
          <thead>
            <tr>
              <th className="sticky left-0 top-0 z-20 w-72 border-b border-r bg-secondary px-4 py-3 text-left font-semibold text-deep">Startup</th>
              {cols.map((c) => (
                <th key={c.key} className={`sticky top-0 z-10 ${c.w} min-w-44 border-b border-r bg-secondary px-4 py-3 text-left font-semibold text-deep`}>{c.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {list.map((r) => (
              <tr key={r.id} className="group align-top">
                <td className="sticky left-0 z-10 border-b border-r bg-card px-4 py-3 group-hover:bg-muted">
                  <div className="flex items-start gap-3">
                    <input
                      type="checkbox"
                      checked={picked.includes(r.id)}
                      disabled={!picked.includes(r.id) && picked.length >= compareLimit}
                      onChange={() => togglePick(r.id)}
                      aria-label={`Compare ${r.name}`}
                      className="mt-1.5 h-4 w-4 shrink-0 accent-primary"
                    />
                    <button
                      type="button"
                      onClick={() => void research.start({ ids: [r.id] })}
                      disabled={research.status?.status === "running" && research.status.current === r.name}
                      className="mt-1 shrink-0 rounded-full bg-ocean px-2.5 py-1 text-[11px] font-medium text-primary-foreground disabled:opacity-60"
                    >
                      {research.status?.status === "running" && research.status.current === r.name ? "Researching…" : "Research"}
                    </button>
                    {r.assessed ? (
                      <ScoreTip row={r}>
                        <span className="inline-flex gap-2">
                          <Score value={r.thesisFit} size={40} />
                          {r.aiThoughts ? <Score value={r.predictedFit} size={40} stroke="stroke-deep" /> : <span className="grid h-10 w-10 place-items-center rounded-full border text-muted-foreground">—</span>}
                        </span>
                      </ScoreTip>
                    ) : <span className="grid h-10 w-10 place-items-center rounded-full border text-muted-foreground">—</span>}
                    <div className="min-w-0">
                      <ScoreTip row={r}>
                        <Link to="/startups/$id" params={{ id: r.id }} className="text-sm font-semibold text-deep hover:text-primary">{r.name}</Link>
                      </ScoreTip>
                      <div className="text-muted-foreground">{r.stage}</div>
                      <button
                        type="button"
                        onClick={() => setThoughtsId(thoughtsId === r.id ? null : r.id)}
                        className="mt-1 text-[11px] font-medium text-primary hover:underline"
                      >
                        AI thoughts
                      </button>
                      {thoughtsId === r.id && (
                        <p className="mt-1 rounded-lg bg-primary-soft p-2 text-[11px] leading-4 text-deep">
                          {r.aiThoughts || "The judge writes the anticipated ranking the next time you research this company."}
                        </p>
                      )}
                    </div>
                  </div>
                </td>
                {cols.map((c) => (
                  <td key={c.key} className="border-b border-r px-4 py-3 leading-relaxed group-hover:bg-muted/50">{c.get(r) || <span className="text-muted-foreground">—</span>}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {startupsQuery.isPending && <p className="py-12 text-center text-muted-foreground">Loading startups…</p>}
        {!startupsQuery.isPending && !startupsQuery.isError && list.length === 0 && (
          <p className="py-12 text-center text-muted-foreground">No startups match your search.</p>
        )}
      </div>

      {open && <IngestDialog onClose={() => setOpen(false)} />}
      {linkOpen && <LinkDialog onClose={() => setLinkOpen(false)} />}
    </Shell>
  );
}

const fields: { key: keyof Profile; label: string; long?: boolean }[] = [
  { key: "website", label: "Website" }, { key: "hq", label: "Headquarters (City, Country)" }, { key: "founders", label: "Founders" },
  { key: "description", label: "One-line description", long: true }, { key: "problem", label: "Problem", long: true },
  { key: "solution", label: "Solution / product", long: true }, { key: "businessModel", label: "Business model" },
  { key: "customers", label: "Target customers" }, { key: "traction", label: "Traction", long: true },
  { key: "funding", label: "Funding history", long: true }, { key: "advantage", label: "Competitive advantage", long: true },
  { key: "competitors", label: "Competitors", long: true }, { key: "thesis", label: "Investment thesis / risks", long: true },
];

function LinkDialog({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const inputCls = "w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring";

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim() || saving) return;
    setSaving(true);
    setError("");
    try {
      const created = await createStartupFromLink({ url: url.trim(), name: name.trim() });
      queryClient.setQueryData(["research"], created.research);
      await queryClient.invalidateQueries({ queryKey: ["startups"] });
      await queryClient.invalidateQueries({ queryKey: ["sectors"] });
      onClose();
    } catch {
      setError("Enter a website link such as https://company.com.");
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-deep/40 p-4 backdrop-blur-sm" onClick={onClose}>
      <form onSubmit={submit} onClick={(e) => e.stopPropagation()} className="w-full max-w-lg rounded-2xl bg-card p-6 shadow-soft">
        <h2 className="text-xl font-semibold text-deep">Add from a link</h2>
        <p className="mb-5 text-sm text-muted-foreground">The company is added now. A research run then fills the table from its website and the public sources.</p>
        <div className="grid gap-4">
          <label className="text-sm">Website link *
            <input required type="text" inputMode="url" placeholder="https://company.com" className={inputCls} value={url} onChange={(e) => setUrl(e.target.value)} />
          </label>
          <label className="text-sm">Name
            <input className={inputCls} value={name} onChange={(e) => setName(e.target.value)} placeholder="Leave blank to take the name from the site" />
          </label>
        </div>
        {error && <p className="mt-4 text-sm text-destructive">{error}</p>}
        <div className="mt-6 flex justify-end gap-3">
          <button type="button" onClick={onClose} className="rounded-full bg-secondary px-5 py-2 text-sm text-secondary-foreground">Cancel</button>
          <button type="submit" disabled={saving} className="rounded-full bg-ocean px-5 py-2 text-sm font-medium text-primary-foreground disabled:opacity-60">
            {saving ? "Starting research…" : "Research and add"}
          </button>
        </div>
      </form>
    </div>
  );
}

function IngestDialog({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [stage, setStage] = useState("Pre-seed");
  const [kw, setKw] = useState("");
  const [p, setP] = useState<Profile>(emptyProfile);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const inputCls = "w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring";

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || saving) return;
    setSaving(true);
    setError("");
    try {
      await createStartup({
        name: name.trim(),
        stage,
        profile: { ...p, keywords: kw.split(",").map((k) => k.trim()).filter(Boolean) },
      });
      await queryClient.invalidateQueries({ queryKey: ["startups"] });
      await queryClient.invalidateQueries({ queryKey: ["sectors"] });
      onClose();
    } catch {
      setError("Could not save this startup. Check that the API is running.");
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-deep/40 p-4 backdrop-blur-sm" onClick={onClose}>
      <form onSubmit={submit} onClick={(e) => e.stopPropagation()} className="max-h-[90vh] w-full max-w-2xl overflow-auto rounded-2xl bg-card p-6 shadow-soft">
        <h2 className="text-xl font-semibold text-deep">Add a new startup</h2>
        <p className="mb-5 text-sm text-muted-foreground">It will appear in the review table right away.</p>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="text-sm">Name *<input required className={inputCls} value={name} onChange={(e) => setName(e.target.value)} /></label>
          <label className="text-sm">Stage
            <select className={inputCls} value={stage} onChange={(e) => setStage(e.target.value)}>
              {["Pre-seed", "Seed", "Series A", "Series B+"].map((s) => <option key={s}>{s}</option>)}
            </select>
          </label>
          <label className="text-sm sm:col-span-2">Industry / keywords (comma separated)<input className={inputCls} value={kw} onChange={(e) => setKw(e.target.value)} placeholder="AI, ClimateTech, B2B" /></label>
          {fields.map((f) => (
            <label key={f.key} className={`text-sm ${f.long ? "sm:col-span-2" : ""}`}>{f.label}
              {f.long
                ? <textarea rows={2} className={inputCls} value={p[f.key] as string} onChange={(e) => setP({ ...p, [f.key]: e.target.value })} />
                : <input className={inputCls} value={p[f.key] as string} onChange={(e) => setP({ ...p, [f.key]: e.target.value })} />}
            </label>
          ))}
        </div>
        {error && <p className="mt-4 text-sm text-destructive">{error}</p>}
        <div className="mt-6 flex justify-end gap-3">
          <button type="button" onClick={onClose} className="rounded-full bg-secondary px-5 py-2 text-sm text-secondary-foreground">Cancel</button>
          <button type="submit" disabled={saving} className="rounded-full bg-ocean px-5 py-2 text-sm font-medium text-primary-foreground disabled:opacity-60">
            {saving ? "Adding…" : "Add to table"}
          </button>
        </div>
      </form>
    </div>
  );
}
