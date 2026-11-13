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
  id: "free" | "student_pro" | "recruiter_pro" | "officer_pro" | "company_pro";
  name: string;
  badge?: string;
  description: string;
  targetRole: "student" | "recruiter" | "placement_officer" | "company" | "all";
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
    ctaLabel: "Free Starter",
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
    badge: "Talent Scout",
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
  officer_pro: {
    id: "officer_pro",
    name: "Placement Officer Pro",
    badge: "Campus Leader",
    description:
      "Empower your college placement cell with batch student imports and corporate hiring invites.",
    targetRole: "placement_officer",
    monthlyPrice: 15,
    annualPrice: 149,
    monthlyCents: 1500,
    annualCents: 14900,
    features: [
      "1-Click batch student CSV imports & automated readiness scoring",
      "Direct Mumbai tech recruiter & HR contact directory",
      "Automated student document pre-verification pipeline",
      "NIRF & NAAC placement audit report generator",
      "Priority college hiring drive broadcasting to employers",
      "Verified Campus Placement Cell official badge",
    ],
    ctaLabel: "Upgrade to Officer Pro ($15/mo)",
    highlighted: true,
  },
  company_pro: {
    id: "company_pro",
    name: "Company Enterprise Pro",
    badge: "Enterprise Grade",
    description:
      "Scale campus hiring drives, manage multi-seat recruitment, and access direct college hotlines.",
    targetRole: "company",
    monthlyPrice: 39,
    annualPrice: 349,
    monthlyCents: 3900,
    annualCents: 34900,
    features: [
      "Multi-seat team hiring pipeline across all Mumbai campuses",
      "Direct TPO & Placement Officer hotline directory",
      "Unlimited candidate discovery, resumes & CGPA filtering",
      "Full verified email & phone unlocks with direct outreach",
      "Automated campus hiring drive announcements",
      "Verified Corporate Employer Diamond badge",
    ],
    ctaLabel: "Upgrade to Company Pro ($39/mo)",
    highlighted: true,
  },
};
