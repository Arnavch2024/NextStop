import { NextRequest, NextResponse } from "next/server";
import { getStripeClient, PRICING_PLANS } from "@/lib/stripe";
import { createClient } from "@supabase/supabase-js";

const SUPABASE_URL =
  process.env.NEXT_PUBLIC_SUPABASE_URL ||
  "https://bsegerbrkbxnosyojmwf.supabase.co";

const SUPABASE_SERVICE_ROLE_KEY =
  process.env.SUPABASE_SERVICE_ROLE_KEY ||
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJzZWdlcmJya2J4bm9zeW9qbXdmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc5Mzk4MTk4NCwiZXhwIjoyMTA5NTU3OTg0fQ.iAoUQ9txINakOxvvLwHvGDSVsELmYGo-lFmOzF56QW4";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { sessionId, plan, userId } = body;

    let targetPlan = plan;
    let targetUserId = userId;
    let customerId: string | null = null;
    let subscriptionId: string | null = null;
    let interval: "month" | "year" = "month";

    // 1. Verify with Stripe if sessionId provided
    if (sessionId) {
      try {
        const stripe = getStripeClient();
        const session = await stripe.checkout.sessions.retrieve(sessionId);

        if (session) {
          if (
            session.payment_status === "paid" ||
            session.status === "complete"
          ) {
            targetPlan = session.metadata?.plan || targetPlan || "student_pro";
            targetUserId =
              session.client_reference_id ||
              session.metadata?.userId ||
              targetUserId;
            customerId = (session.customer as string) || null;
            subscriptionId = (session.subscription as string) || null;
            if (session.metadata?.interval === "year") {
              interval = "year";
            }
          }
        }
      } catch (stripeErr: any) {
        console.warn(
          "Could not verify session directly with Stripe (proceeding with fallback):",
          stripeErr?.message
        );
      }
    }

    if (!targetUserId || targetUserId === "anonymous") {
      return NextResponse.json(
        { error: "User ID is required to activate subscription." },
        { status: 400 }
      );
    }

    if (
      !targetPlan ||
      !["student_pro", "recruiter_pro", "officer_pro", "company_pro"].includes(
        targetPlan
      )
    ) {
      return NextResponse.json(
        { error: "Invalid subscription plan." },
        { status: 400 }
      );
    }

    // 2. Update Supabase with service role
    const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, {
      auth: { persistSession: false },
    });

    // Update profiles table
    const { data: updatedProfile, error: profileErr } = await supabase
      .from("profiles")
      .update({
        subscription_tier: targetPlan,
        stripe_customer_id: customerId,
        stripe_subscription_id: subscriptionId,
        updated_at: new Date().toISOString(),
      })
      .eq("id", targetUserId)
      .select("id, role, subscription_tier, display_name")
      .single();

    if (profileErr) {
      console.error("Failed to update profile subscription_tier:", profileErr);
    }

    // Upsert into subscriptions table
    try {
      await supabase.from("subscriptions").upsert(
        {
          user_id: targetUserId,
          plan: targetPlan,
          billing_interval: interval,
          status: "active",
          stripe_customer_id: customerId,
          stripe_subscription_id: subscriptionId,
          updated_at: new Date().toISOString(),
        },
        { onConflict: "user_id" }
      );
    } catch (subErr) {
      console.warn("Could not upsert into subscriptions table:", subErr);
    }

    // Record audit event in raw_events
    try {
      await supabase.from("raw_events").insert({
        actor_id: targetUserId,
        source: "stripe_subscription",
        payload: {
          plan: targetPlan,
          status: "active",
          stripe_session_id: sessionId || null,
          stripe_customer_id: customerId,
          stripe_subscription_id: subscriptionId,
          interval,
          activated_at: new Date().toISOString(),
        },
      });
    } catch {
      // Non-blocking
    }

    const planConfig = PRICING_PLANS[targetPlan];

    return NextResponse.json({
      success: true,
      tier: targetPlan,
      planName: planConfig?.name || targetPlan,
      user: updatedProfile,
    });
  } catch (err: any) {
    console.error("Subscription activation failed:", err);
    return NextResponse.json(
      { error: err?.message || "Failed to activate subscription." },
      { status: 500 }
    );
  }
}
