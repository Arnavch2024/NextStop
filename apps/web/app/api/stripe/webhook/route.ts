import { NextRequest, NextResponse } from "next/server";
import { getStripeClient } from "@/lib/stripe";
import { createClient } from "@supabase/supabase-js";

const SUPABASE_URL =
  process.env.NEXT_PUBLIC_SUPABASE_URL ||
  "https://bsegerbrkbxnosyojmwf.supabase.co";

const SUPABASE_SERVICE_ROLE_KEY =
  process.env.SUPABASE_SERVICE_ROLE_KEY ||
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJzZWdlcmJya2J4bm9zeW9qbXdmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc5Mzk4MTk4NCwiZXhwIjoyMTA5NTU3OTg0fQ.iAoUQ9txINakOxvvLwHvGDSVsELmYGo-lFmOzF56QW4";

export async function POST(req: NextRequest) {
  try {
    const rawBody = await req.text();
    const signature = req.headers.get("stripe-signature");
    const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET;

    const stripe = getStripeClient();
    let event: any;

    if (webhookSecret && signature) {
      try {
        event = stripe.webhooks.constructEvent(
          rawBody,
          signature,
          webhookSecret
        );
      } catch (err: any) {
        console.error("Webhook signature verification failed:", err.message);
        return NextResponse.json(
          { error: `Webhook Signature Error: ${err.message}` },
          { status: 400 }
        );
      }
    } else {
      // In development or test sandbox without webhook secret, parse payload directly
      try {
        event = JSON.parse(rawBody);
      } catch {
        return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
      }
    }

    // Handle checkout completion
    if (event.type === "checkout.session.completed") {
      const session = event.data.object;
      const userId = session.client_reference_id || session.metadata?.userId;
      const plan = session.metadata?.plan || "student_pro";
      const interval = session.metadata?.interval === "year" ? "year" : "month";

      console.log(
        `[Stripe Webhook] Checkout completed for user ${userId}, plan ${plan}`
      );

      // Record in Supabase if userId is provided
      if (userId && userId !== "anonymous") {
        try {
          const supabase = createClient(
            SUPABASE_URL,
            SUPABASE_SERVICE_ROLE_KEY,
            { auth: { persistSession: false } }
          );

          // 1. Update profiles table
          await supabase
            .from("profiles")
            .update({
              subscription_tier: plan,
              stripe_customer_id: session.customer,
              stripe_subscription_id: session.subscription,
              updated_at: new Date().toISOString(),
            })
            .eq("id", userId);

          // 2. Upsert into subscriptions table
          try {
            await supabase.from("subscriptions").upsert(
              {
                user_id: userId,
                plan: plan,
                billing_interval: interval,
                status: "active",
                stripe_customer_id: session.customer,
                stripe_subscription_id: session.subscription,
                updated_at: new Date().toISOString(),
              },
              { onConflict: "user_id" }
            );
          } catch (subErr) {
            console.warn("Webhook subscriptions table upsert error:", subErr);
          }

          // 3. Insert into raw_events
          await supabase.from("raw_events").insert({
            actor_id: userId,
            source: "stripe_subscription",
            payload: {
              plan: plan,
              status: "active",
              stripe_session_id: session.id,
              stripe_customer_id: session.customer,
              stripe_subscription_id: session.subscription,
              amount_total: session.amount_total,
              currency: session.currency,
              created_at: new Date().toISOString(),
            },
          });
        } catch (dbErr) {
          console.warn(
            "Could not write subscription event to Supabase:",
            dbErr
          );
        }
      }
    }

    return NextResponse.json({ received: true });
  } catch (err: any) {
    console.error("Stripe webhook handler error:", err);
    return NextResponse.json(
      { error: err.message || "Webhook handler failed" },
      { status: 500 }
    );
  }
}
