"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

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
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
