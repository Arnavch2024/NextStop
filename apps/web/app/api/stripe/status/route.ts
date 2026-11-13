import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { PRICING_PLANS } from "@/lib/stripe";

const SUPABASE_URL =
  process.env.NEXT_PUBLIC_SUPABASE_URL ||
  "https://bsegerbrkbxnosyojmwf.supabase.co";

const SUPABASE_SERVICE_ROLE_KEY =
  process.env.SUPABASE_SERVICE_ROLE_KEY ||
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJzZWdlcmJya2J4bm9zeW9qbXdmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc5Mzk4MTk4NCwiZXhwIjoyMTA5NTU3OTg0fQ.iAoUQ9txINakOxvvLwHvGDSVsELmYGo-lFmOzF56QW4";

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

    const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, {
      auth: { persistSession: false },
    });

    // 1. Check profiles table
    const { data: profile } = await supabase
      .from("profiles")
      .select("subscription_tier")
      .eq("id", userId)
      .single();

    if (
      profile?.subscription_tier &&
      ["student_pro", "recruiter_pro", "officer_pro", "company_pro"].includes(
        profile.subscription_tier
      )
    ) {
      const planConfig = PRICING_PLANS[profile.subscription_tier];
      return NextResponse.json({
        tier: profile.subscription_tier,
        isPro: true,
        planName: planConfig?.name || profile.subscription_tier,
      });
    }

    // 2. Check subscriptions table
    const { data: sub } = await supabase
      .from("subscriptions")
      .select("plan, status")
      .eq("user_id", userId)
      .eq("status", "active")
      .order("created_at", { ascending: false })
      .limit(1)
      .maybeSingle();

    if (sub?.plan) {
      const planConfig = PRICING_PLANS[sub.plan];
      return NextResponse.json({
        tier: sub.plan,
        isPro: true,
        planName: planConfig?.name || sub.plan,
      });
    }

    // 3. Check raw_events as last fallback
    const { data: events } = await supabase
      .from("raw_events")
      .select("payload, created_at")
      .eq("actor_id", userId)
      .eq("source", "stripe_subscription")
      .order("created_at", { ascending: false })
      .limit(1);

    if (events && events.length > 0 && events[0].payload?.status === "active") {
      const plan = events[0].payload?.plan || "student_pro";
      const planConfig = PRICING_PLANS[plan];
      return NextResponse.json({
        tier: plan,
        isPro: true,
        planName: planConfig?.name || plan,
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
