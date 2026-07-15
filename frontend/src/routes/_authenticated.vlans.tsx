import { createFileRoute } from "@tanstack/react-router";
import { VlansPage } from "@/features/vlans/VlansPage";

export const Route = createFileRoute("/_authenticated/vlans")({
  component: VlansPage,
});
