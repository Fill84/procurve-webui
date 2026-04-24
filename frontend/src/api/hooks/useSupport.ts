import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/api/client";
import type { components } from "@/api/schema";

type SupportInfo = components["schemas"]["SupportInfo"];

export function useSupport() {
  return useQuery<SupportInfo>({
    queryKey: ["support"],
    queryFn: () => apiGet<SupportInfo>("/api/v1/support"),
    staleTime: Infinity, // static content
  });
}
