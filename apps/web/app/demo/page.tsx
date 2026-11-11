import { notFound } from "next/navigation";
import { isDemoEnabled } from "@/lib/config";
import DemoPickerClient from "./DemoPickerClient";

export const metadata = {
  title: "Demo Personas | Campus Recruiting",
  description:
    "Explore the campus recruiting platform through pre-seeded role personas.",
};

export default function DemoPage() {
  if (!isDemoEnabled()) {
    notFound();
  }

  return <DemoPickerClient />;
}
