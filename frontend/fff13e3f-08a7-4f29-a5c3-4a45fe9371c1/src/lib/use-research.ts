import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { getResearch, startResearch, type ResearchStatus } from "@/lib/api";

export function useResearch(): {
  status: ResearchStatus | undefined;
  start: (request?: { names?: string[]; ids?: string[] }) => Promise<void>;
} {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["research"],
    queryFn: getResearch,
    refetchInterval: (current) => (current.state.data?.status === "running" ? 2000 : false),
  });
  const finishedAt = query.data?.finishedAt ?? "";

  useEffect(() => {
    if (!finishedAt) return;
    void queryClient.invalidateQueries({ queryKey: ["startups"] });
    void queryClient.invalidateQueries({ queryKey: ["startup"] });
    void queryClient.invalidateQueries({ queryKey: ["sectors"] });
  }, [finishedAt, queryClient]);

  return {
    status: query.data,
    start: async (request: { names?: string[]; ids?: string[] } = {}) => {
      const next = await startResearch(request);
      queryClient.setQueryData(["research"], next);
    },
  };
}
