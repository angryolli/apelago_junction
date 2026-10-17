import type { Profile, Row } from "@/data/radar";

export type ResearchStatus = {
  status: "idle" | "running" | "done" | "error";
  message: string;
  current: string;
  completed: string[];
  errors: string[];
  finishedAt: string;
};

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function apiBase(): string {
  if (typeof window !== "undefined") {
    return "";
  }

  const env = (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env;

  return env?.API_URL || "http://127.0.0.1:8000";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set("Accept", "application/json");
  if (init?.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${apiBase()}${path}`, { ...init, headers });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json() as { detail?: unknown };
      if (typeof body.detail === "string" && body.detail) message = body.detail;
    } catch {
      /* The status line is enough when the body is not JSON. */
    }
    throw new ApiError(response.status, message);
  }

  return response.json() as Promise<T>;
}

export function listStartups(filters: { q: string; sector: string }): Promise<Row[]> {
  const params = new URLSearchParams();
  const query = filters.q.trim();
  if (query) params.set("q", query);
  if (filters.sector) params.set("sector", filters.sector);
  const search = params.toString();

  return request<Row[]>(search ? `/api/startups?${search}` : "/api/startups");
}

export function listSectors(): Promise<string[]> {
  return request<string[]>("/api/sectors");
}

export function getStartup(id: string): Promise<Row> {
  return request<Row>(`/api/startups/${encodeURIComponent(id)}`);
}

export function getResearch(): Promise<ResearchStatus> {
  return request<ResearchStatus>("/api/research");
}

export function startResearch(body: { names?: string[]; ids?: string[] } = {}): Promise<ResearchStatus> {
  return request<ResearchStatus>("/api/research", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export type LinkStartupResult = {
  startup: Row;
  research: ResearchStatus;
};

export function createStartupWithDeck(body: { url: string; name?: string; deck?: File | null }): Promise<LinkStartupResult> {
  const form = new FormData();
  form.set("url", body.url);
  form.set("name", body.name ?? "");
  if (body.deck) form.set("deck", body.deck);

  return request<LinkStartupResult>("/api/startups/with-deck", {
    method: "POST",
    body: form,
  });
}

export function createStartupFromLink(body: { url: string; name?: string }): Promise<LinkStartupResult> {
  return request<LinkStartupResult>("/api/startups/from-link", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export type CompareResult = {
  preferredId: string;
  preferredName: string;
  explanation: string;
};

export function compareStartups(body: { ids: string[]; thesis: string }): Promise<CompareResult> {
  return request<CompareResult>("/api/compare", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export type ExplorePick = {
  name: string;
  why: string;
  country: string;
  website: string;
};

export type Inquiry = {
  questions: string[];
  risks: string[];
  introductions: string[];
  opportunities: string[];
};

export function createInquiry(id: string): Promise<Inquiry> {
  return request<Inquiry>(`/api/startups/${encodeURIComponent(id)}/inquiry`, { method: "POST" });
}

export function exploreStartup(): Promise<ExplorePick> {
  return request<ExplorePick>("/api/explore", { method: "POST" });
}

export function createStartup(body: { name: string; stage: string; profile: Profile }): Promise<Row> {
  return request<Row>("/api/startups", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
