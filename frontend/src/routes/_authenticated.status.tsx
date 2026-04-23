import { createFileRoute } from "@tanstack/react-router";
import { StatusOverviewPage } from "@/features/status/StatusOverviewPage";

export const Route = createFileRoute("/_authenticated/status")({
  component: StatusOverviewPage,
});
