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
