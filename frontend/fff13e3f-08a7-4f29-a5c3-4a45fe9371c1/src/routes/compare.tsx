import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Shell } from "@/components/Shell";
import type { Row } from "@/data/radar";
import { compareStartups, getStartup } from "@/lib/api";

export const theses = [
  "Early-stage Baltic and European blue economy",
  "Ocean impact with a measurable marine benefit",
  "Defensible technology close to deployment",
  "Commercial traction and investment readiness",
] as const;

type CompareSearch = {
  ids: string;
  thesis: string;
};

export const Route = createFileRoute("/compare")({
  validateSearch: (search: Record<string, unknown>): CompareSearch => ({
    ids: typeof search.ids === "string" ? search.ids : "",
    thesis: typeof search.thesis === "string" && search.thesis.trim() ? search.thesis : theses[0],
  }),
  head: () => ({
    meta: [
      { title: "Compare startups — Ocean Opportunity Radar" },
      { name: "description", content: "Compare ocean impact, readiness, growth, risks, and funding." },
    ],
  }),
  component: ComparePage,
});

const levels: { label: string; read: (row: Row) => number }[] = [
  { label: "Ocean impact", read: (row) => row.readiness.impact },
  { label: "BRL", read: (row) => row.readiness.business },
  { label: "TRL", read: (row) => row.readiness.tech },
  { label: "Investment readiness", read: (row) => row.readiness.investment },
];

function leaders(rows: Row[], read: (row: Row) => number): Set<string> {
  const scores = rows.map((row) => read(row));
  const best = Math.max(...scores);
  if (scores.every((score) => score === best)) return new Set();
  return new Set(rows.filter((row) => read(row) === best).map((row) => row.id));
}

function ComparePage() {
  const search = Route.useSearch();
  const navigate = Route.useNavigate();
  const ids = search.ids.split(",").map((item) => item.trim()).filter(Boolean).slice(0, 4);
  const companiesQuery = useQuery({
    queryKey: ["compare-companies", ids.join(",")],
    queryFn: () => Promise.all(ids.map((id) => getStartup(id))),
    enabled: ids.length >= 2,
  });
  const verdictQuery = useQuery({
    queryKey: ["compare-verdict", ids.join(","), search.thesis],
    queryFn: () => compareStartups({ ids, thesis: search.thesis }),
    enabled: ids.length >= 2,
  });
  const companies = companiesQuery.data ?? [];

  return (
    <Shell wide>
      <Link to="/" className="text-sm text-primary hover:underline">Back to the review</Link>
      <h1 className="mt-3 text-3xl font-semibold text-deep">Compare startups</h1>
      <p className="mt-1 text-sm text-muted-foreground">Ocean impact, BRL, TRL, growth, risks, funding, and investment readiness.</p>

      {ids.length < 2 && (
        <p className="mt-6 text-sm text-muted-foreground">Select two to four startups from the review table.</p>
      )}

      {ids.length >= 2 && (
        <>
          <label className="mt-6 block text-sm font-medium text-deep">
            Investor thesis
            <select
              value={search.thesis}
              onChange={(event) => void navigate({ search: { ids: search.ids, thesis: event.target.value } })}
              className="mt-2 block h-10 w-full max-w-xl rounded-full border bg-card px-4 text-sm outline-none focus:ring-2 focus:ring-ring"
            >
              {theses.map((thesis) => <option key={thesis} value={thesis}>{thesis}</option>)}
              {!theses.includes(search.thesis as (typeof theses)[number]) && (
                <option value={search.thesis}>{search.thesis}</option>
              )}
            </select>
          </label>

          <section className="mt-6 rounded-2xl bg-ocean p-6 text-primary-foreground shadow-soft">
            <p className="text-xs uppercase tracking-widest opacity-80">Better match</p>
            {verdictQuery.isPending && <p className="mt-2 text-lg">Writing the thesis comparison…</p>}
            {verdictQuery.isError && (
              <p className="mt-2 text-sm">The thesis comparison could not be written. The scores below are still the stored assessment.</p>
            )}
            {verdictQuery.data && (
              <>
                <h2 className="mt-2 text-2xl font-semibold">{verdictQuery.data.preferredName}</h2>
                <p className="mt-3 max-w-3xl text-sm leading-relaxed">{verdictQuery.data.explanation}</p>
              </>
            )}
          </section>

          {companiesQuery.isError && (
            <p className="mt-6 text-sm text-destructive">Those startups could not be loaded.</p>
          )}

          {companies.length > 0 && (
            <div className="mt-6 overflow-auto rounded-2xl border bg-card">
              <table className="w-full border-separate border-spacing-0 text-sm">
                <thead>
                  <tr>
                    <th className="sticky left-0 z-10 min-w-44 border-b border-r bg-secondary px-4 py-3 text-left font-semibold text-deep" />
                    {companies.map((company) => (
                      <th
                        key={company.id}
                        className={`min-w-56 border-b border-r px-4 py-3 text-left ${verdictQuery.data?.preferredId === company.id ? "bg-primary-soft" : "bg-secondary"}`}
                      >
                        <Link to="/startups/$id" params={{ id: company.id }} className="font-semibold text-deep hover:text-primary">
                          {company.name}
                        </Link>
                        <div className="mt-1 text-xs font-normal text-muted-foreground">
                          {company.assessed ? `Thesis fit ${company.thesisFit}/100` : "Not scored"}
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {levels.map((level) => {
                    const ahead = leaders(companies, level.read);
                    return (
                      <tr key={level.label}>
                        <th className="sticky left-0 border-b border-r bg-card px-4 py-3 text-left font-medium text-deep">{level.label}</th>
                        {companies.map((company) => (
                          <td key={company.id} className={`border-b border-r px-4 py-3 ${ahead.has(company.id) ? "bg-primary-soft font-medium text-deep" : ""}`}>
                            {level.read(company)}/9
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                  <tr>
                    <th className="sticky left-0 border-b border-r bg-card px-4 py-3 text-left align-top font-medium text-deep">Growth</th>
                    {companies.map((company) => (
                      <td key={company.id} className="border-b border-r px-4 py-3 align-top text-muted-foreground">
                        {company.profile.traction || "Not recorded"}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <th className="sticky left-0 border-b border-r bg-card px-4 py-3 text-left align-top font-medium text-deep">Risks</th>
                    {companies.map((company) => (
                      <td key={company.id} className="border-b border-r px-4 py-3 align-top">
                        {company.risks.length === 0 ? (
                          <span className="text-muted-foreground">None recorded</span>
                        ) : (
                          <ul className="list-disc space-y-1 pl-4 text-muted-foreground">
                            {company.risks.map((risk) => <li key={risk}>{risk}</li>)}
                          </ul>
                        )}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <th className="sticky left-0 border-b border-r bg-card px-4 py-3 text-left align-top font-medium text-deep">Funding</th>
                    {companies.map((company) => (
                      <td key={company.id} className="border-b border-r px-4 py-3 align-top text-muted-foreground">
                        {company.profile.funding || company.raised || "Not recorded"}
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </Shell>
  );
}
