import { NextResponse } from "next/server";
import { isDemoEnabled } from "@/lib/config";

export async function GET() {
  return NextResponse.json({
    demo_enabled: isDemoEnabled(),
  });
}
