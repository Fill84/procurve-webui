import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/api/client";
import type { components } from "@/api/schema";

type Identity = components["schemas"]["DeviceIdentity"];

export function useIdentity() {
  return useQuery<Identity>({
    queryKey: ["identity"],
    queryFn: () => apiGet<Identity>("/api/v1/identity"),
  });
}
