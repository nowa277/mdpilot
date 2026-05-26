import { fetchHealth } from '@shared/api';
import { Button } from '@shared/ui';
import { useQuery } from '@tanstack/react-query';
import { type PropsWithChildren } from 'react';

export function HealthGate({ children }: PropsWithChildren) {
  const query = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    retry: 1,
    refetchOnWindowFocus: false,
    staleTime: 60_000,
  });

  if (query.isPending) {
    return (
      <div className="flex h-screen items-center justify-center bg-bg-0 text-text-2">
        Connecting to lab03 backend…
      </div>
    );
  }

  if (query.isError || !['ok', 'healthy'].includes(query.data?.status ?? '')) {
    return (
      <div className="flex h-screen items-center justify-center bg-bg-0">
        <div className="flex max-w-md flex-col gap-4 rounded-panel border border-1 bg-bg-1 p-8 text-center">
          <h1 className="font-display text-2xl text-text-1">Unable to connect to lab03 backend</h1>
          <p className="text-sm text-text-2">
          Check if lab03 is online, or run in mock mode (VITE_API_MODE=mock).
          </p>
          <div className="flex justify-center">
            <Button onClick={() => void query.refetch()}>Retry</Button>
       </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
