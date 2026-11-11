"use client";

import { useRouter } from "next/navigation";
import { logout } from "@/lib/auth";
import { RotateCcw } from "lucide-react";

interface SwitchDemoRoleButtonProps {
  className?: string;
}

export function SwitchDemoRoleButton({
  className = "",
}: SwitchDemoRoleButtonProps) {
  const router = useRouter();

  async function handleSwitch() {
    await logout();
    router.replace("/demo");
  }

  return (
    <button
      type="button"
      onClick={handleSwitch}
      className={`inline-flex items-center gap-1.5 rounded-xl border border-amber-300 bg-amber-50 px-3 py-1.5 text-xs font-semibold text-amber-900 transition hover:bg-amber-100 shadow-2xs ${className}`}
      title="Sign out and switch demo role"
    >
      <RotateCcw className="h-3.5 w-3.5 text-amber-700" />
      <span>Switch demo role</span>
    </button>
  );
}
