import { createFileRoute } from "@tanstack/react-router";
import { ConfigurationPage } from "@/features/configuration/ConfigurationPage";

export const Route = createFileRoute("/_authenticated/configuration")({
  component: ConfigurationPage,
});
