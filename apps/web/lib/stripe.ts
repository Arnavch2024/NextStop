import Stripe from "stripe";

// Lazily initialize Stripe server client
let stripeClient: Stripe | null = null;

export function getStripeClient(): Stripe {
  if (!stripeClient) {
    const key = process.env.STRIPE_SECRET_KEY;
    if (!key) {
      throw new Error(
        "STRIPE_SECRET_KEY is not configured in environment variables."
      );
    }
    stripeClient = new Stripe(key, {
      apiVersion: "2024-04-10" as any,
      typescript: true,
    });
  }
  return stripeClient;
}

export interface PricingPlan {
  id: "free" | "student_pro" | "recruiter_pro";
  name: string;
  badge?: string;
  description: string;
  targetRole: "student" | "recruiter" | "all";
  monthlyPrice: number; // in USD
  annualPrice: number; // in USD (discounted)
  monthlyCents: number;
  annualCents: number;
  features: string[];
  ctaLabel: string;
  highlighted?: boolean;
}

export const PRICING_PLANS: Record<string, PricingPlan> = {
  free: {
    id: "free",
    name: "Starter",
    description: "Essential AI recruiting tools for individual candidates.",
    targetRole: "all",
    monthlyPrice: 0,
    annualPrice: 0,
    monthlyCents: 0,
    annualCents: 0,
    features: [
      "1 AI Resume parse & readiness evaluation",
      "Standard candidate profile & milestone railway",
      "Up to 5 campus recruiter directory searches / day",
      "Standard community response speed",
    ],
    ctaLabel: "Current Plan",
    highlighted: false,
  },
  student_pro: {
    id: "student_pro",
    name: "Student Pro",
    badge: "Most Popular",
    description:
      "Accelerate your campus placement readiness and get discovered.",
    targetRole: "student",
    monthlyPrice: 3,
    annualPrice: 29,
    monthlyCents: 300,
    annualCents: 2900,
    features: [
      "Unlimited AI recruiter chat & intelligence answers",
      "Unlimited AI resume updates & instant score boosts",
      "Priority recruiter discovery & placement spotlight",
      "Shiny Pro Candidate Gold Badge across your profile",
      "Employer reference check authorization support",
      "Personalized outreach message generator",
    ],
    ctaLabel: "Upgrade to Student Pro ($3/mo)",
    highlighted: true,
  },
  recruiter_pro: {
    id: "recruiter_pro",
    name: "Recruiter Pro",
    badge: "Enterprise Grade",
    description: "Unlock top engineering talent across Mumbai colleges.",
    targetRole: "recruiter",
    monthlyPrice: 19,
    annualPrice: 189,
    monthlyCents: 1900,
    annualCents: 18900,
    features: [
      "Unlimited candidate discovery & CGPA filtering",
      "Verified direct phone & email unlocks",
      "AI-generated personalized email & LinkedIn outreach",
      "Placement officer contact directory across Mumbai",
      "1-Click CSV candidate pipeline export",
      "Verified Pro Recruiter badge with direct student trust",
    ],
    ctaLabel: "Upgrade to Recruiter Pro ($19/mo)",
    highlighted: true,
  },
};
