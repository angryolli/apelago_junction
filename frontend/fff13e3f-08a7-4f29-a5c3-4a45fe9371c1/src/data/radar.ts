export type Readiness = { impact: number; business: number; tech: number; investment: number };
export type Dimension = { name: string; score: number; note: string };
export type Match = { name: string; type: "Investor" | "Grant" | "Partner" | "Client"; fit: number; why: string; region: string };
export type SourceHit = {
  source: "website" | "dealroom" | "blueinvest" | "business_finland" | "prh" | "cordis";
  title: string;
  url: string;
  excerpt: string;
  found: boolean;
};

export type Startup = {
  id: string;
  name: string;
  tagline: string;
  sector: string;
  country: string;
  stage: string;
  founded: number;
  raised: string;
  team: number;
  thesisFit: number;
  predictedFit: number;
  aiThoughts: string;
  scoreExplanation: string;
  readiness: Readiness;
  dimensions: Dimension[];
  signals: string[];
  risks: string[];
  matches: Match[];
  nextSteps: string[];
  sources: SourceHit[];
  assessed: boolean;
  judgeVerdict: string;
  judgeNotes: string;
};

export type Profile = {
  website: string;
  hq: string;
  founders: string;
  email: string;
  description: string;
  keywords: string[];
  problem: string;
  solution: string;
  businessModel: string;
  customers: string;
  traction: string;
  funding: string;
  advantage: string;
  competitors: string;
  thesis: string;
};

export type Row = Startup & { profile: Profile };

export const emptyProfile: Profile = {
  website: "",
  hq: "",
  founders: "",
  email: "",
  description: "",
  keywords: [],
  problem: "",
  solution: "",
  businessModel: "",
  customers: "",
  traction: "",
  funding: "",
  advantage: "",
  competitors: "",
  thesis: "",
};
