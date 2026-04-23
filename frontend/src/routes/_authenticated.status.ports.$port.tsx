import { createFileRoute } from "@tanstack/react-router";
import { PortDetailPage } from "@/features/status/PortDetailPage";

export const Route = createFileRoute("/_authenticated/status/ports/$port")({
  component: PortDetailRoute,
});

function PortDetailRoute() {
  const { port } = Route.useParams();
  return <PortDetailPage port={port} />;
}
