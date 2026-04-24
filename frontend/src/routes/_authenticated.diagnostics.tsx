import { createFileRoute } from "@tanstack/react-router";
import { DiagnosticsPage } from "@/features/diagnostics/DiagnosticsPage";

export const Route = createFileRoute("/_authenticated/diagnostics")({
  component: DiagnosticsPage,
});
