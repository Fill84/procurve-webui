import { createFileRoute } from "@tanstack/react-router";
import { ComingLaterPage } from "@/features/coming-later/ComingLaterPage";

export const Route = createFileRoute("/_authenticated/configuration")({
  component: () => <ComingLaterPage tabName="Configuration" />,
});
