import { NextRequest, NextResponse } from "next/server";
import { getStripeClient, PRICING_PLANS } from "@/lib/stripe";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { plan, interval = "month", userId, userEmail, returnOrigin } = body;

    const planConfig = PRICING_PLANS[plan];
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
      interval === "year" ? planConfig.annualCents : planConfig.monthlyCents;
    const intervalValue = interval === "year" ? "year" : "month";

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
              interval: intervalValue,
            },
          },
          quantity: 1,
        },
      ],
      mode: "subscription",
      allow_promotion_codes: true,
      billing_address_collection: "auto",
      success_url: `${origin}/pricing?success=true&plan=${plan}&session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${origin}/pricing?canceled=true`,
      metadata: {
        userId: userId || "anonymous",
        plan: plan,
        interval: intervalValue,
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
    });
  } catch (err: any) {
    console.error("Stripe checkout session creation failed:", err);
    return NextResponse.json(
      { error: err.message || "Failed to create checkout session." },
      { status: 500 }
    );
  }
}
