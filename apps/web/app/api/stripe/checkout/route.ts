import { NextRequest, NextResponse } from "next/server";
import { getStripeClient, PRICING_PLANS } from "@/lib/stripe";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const {
      plan,
      planId,
      interval,
      billingCycle,
      userId,
      userEmail,
      returnOrigin,
    } = body;

    const selectedPlan = plan || planId;
    const rawInterval = interval || billingCycle || "month";
    const normalizedInterval =
      rawInterval === "annual" || rawInterval === "year" ? "year" : "month";

    const planConfig = PRICING_PLANS[selectedPlan];
    if (!planConfig || planConfig.id === "free") {
      return NextResponse.json(
        { error: "Invalid plan selected for checkout." },
        { status: 400 }
      );
    }

    // Role enforcement: ensure logged-in user only purchases their own persona's plan
    if (userId) {
      try {
        const { getSupabaseBrowserClient } = await import("@/lib/supabase");
        // Use direct Supabase query with admin/service role if available or fallback
        const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
        const supabaseKey =
          process.env.SUPABASE_SERVICE_ROLE_KEY ||
          process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
        if (supabaseUrl && supabaseKey) {
          const { createClient } = await import("@supabase/supabase-js");
          const supabase = createClient(supabaseUrl, supabaseKey);
          const { data: profile } = await supabase
            .from("profiles")
            .select("role")
            .eq("id", userId)
            .single();

          if (profile?.role && planConfig.targetRole !== "all") {
            if (profile.role !== planConfig.targetRole) {
              return NextResponse.json(
                {
                  error: `Your account role is '${profile.role}'. You can only subscribe to plans for your specific role.`,
                },
                { status: 403 }
              );
            }
          }
        }
      } catch (valErr) {
        console.warn("Could not validate user role for plan:", valErr);
      }
    }

    const stripe = getStripeClient();
    const origin =
      returnOrigin ||
      req.headers.get("origin") ||
      process.env.NEXT_PUBLIC_APP_URL ||
      "https://nextstop-web.vercel.app";

    const unitAmount =
      normalizedInterval === "year"
        ? planConfig.annualCents
        : planConfig.monthlyCents;

    const sessionParams: any = {
      payment_method_types: ["card"],
      line_items: [
        {
          price_data: {
            currency: "usd",
            product_data: {
              name: `NextStop ${planConfig.name}`,
              description: planConfig.description,
            },
            unit_amount: unitAmount,
            recurring: {
              interval: normalizedInterval,
            },
          },
          quantity: 1,
        },
      ],
      mode: "subscription",
      allow_promotion_codes: true,
      billing_address_collection: "auto",
      success_url: `${origin}/pricing?success=true&plan=${selectedPlan}&session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${origin}/pricing?canceled=true`,
      metadata: {
        userId: userId || "anonymous",
        plan: selectedPlan,
        interval: normalizedInterval,
      },
    };

    if (userEmail && userEmail.includes("@")) {
      sessionParams.customer_email = userEmail;
    }

    if (userId) {
      sessionParams.client_reference_id = userId;
    }

    const session = await stripe.checkout.sessions.create(sessionParams);

    return NextResponse.json({
      sessionId: session.id,
      url: session.url,
      checkoutUrl: session.url,
    });
  } catch (err: any) {
    console.error("Stripe checkout session creation failed:", err);
    return NextResponse.json(
      { error: err.message || "Failed to create checkout session." },
      { status: 500 }
    );
  }
}
