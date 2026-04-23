import { createFileRoute } from "@tanstack/react-router";
import { BackupsListPage } from "@/features/backups/BackupsListPage";

export const Route = createFileRoute("/_authenticated/backups")({
  component: BackupsListPage,
});
