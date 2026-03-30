"use client";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { useState } from "react";

// Silently pings /api/health every 4 minutes to keep Neon compute from auto-suspending.
// This prevents mid-session connection drops when the user rests between sets.
function KeepAlive() {
  useQuery({
    queryKey: ["keep-alive"],
    queryFn: () => fetch("/api/health").then((r) => r.json()),
    refetchInterval: 4 * 60 * 1000,
    refetchIntervalInBackground: false,
    staleTime: Infinity,
    retry: 0,
  });
  return null;
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: 5,
            retryDelay: (attempt) => Math.min(2000 * 2 ** attempt, 15000),
            refetchOnWindowFocus: false,
          },
          mutations: {
            retry: 3,
            retryDelay: (attempt) => Math.min(2000 * 2 ** attempt, 10000),
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <KeepAlive />
      {children}
    </QueryClientProvider>
  );
}
