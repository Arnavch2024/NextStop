"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getCurrentSession, getRoleDashboardPath } from "@/lib/auth";

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    getCurrentSession().then((session) => {
      if (!session) {
        router.replace("/login");
        return;
      }
      router.replace(getRoleDashboardPath(session.user.role));
    });
  }, [router]);

  return (
    <div className="flex h-screen items-center justify-center bg-slate-50">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent" />
    </div>
  );
}
