import { NextRequest, NextResponse } from "next/server";
import { getStripeClient } from "@/lib/stripe";
import { getSupabaseBrowserClient } from "@/lib/supabase";

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
      } catch (e) {
        return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
      }
    }

    // Handle checkout completion
    if (event.type === "checkout.session.completed") {
      const session = event.data.object;
      const userId = session.client_reference_id || session.metadata?.userId;
      const plan = session.metadata?.plan || "student_pro";

      console.log(
        `[Stripe Webhook] Checkout completed for user ${userId}, plan ${plan}`
      );

      // Record in Supabase if userId is provided
      if (userId && userId !== "anonymous") {
        try {
          const supabase = getSupabaseBrowserClient();
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
