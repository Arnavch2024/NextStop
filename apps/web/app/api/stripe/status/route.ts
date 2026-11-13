import { NextRequest, NextResponse } from "next/server";
import { getSupabaseBrowserClient } from "@/lib/supabase";

export async function GET(req: NextRequest) {
  try {
    const userId = req.nextUrl.searchParams.get("userId");
    if (!userId) {
      return NextResponse.json({
        tier: "free",
        isPro: false,
        planName: "Starter",
      });
    }

    const supabase = getSupabaseBrowserClient();
    const { data: events } = await supabase
      .from("raw_events")
      .select("payload, created_at")
      .eq("actor_id", userId)
      .eq("source", "stripe_subscription")
      .order("created_at", { ascending: false })
      .limit(1);

    if (events && events.length > 0 && events[0].payload?.status === "active") {
      const plan = events[0].payload?.plan || "student_pro";
      return NextResponse.json({
        tier: plan,
        isPro: true,
        planName: plan === "recruiter_pro" ? "Recruiter Pro" : "Student Pro",
        subscribedAt: events[0].created_at,
      });
    }

    return NextResponse.json({
      tier: "free",
      isPro: false,
      planName: "Starter",
    });
  } catch (err: any) {
    return NextResponse.json({
      tier: "free",
      isPro: false,
      planName: "Starter",
    });
  }
}
