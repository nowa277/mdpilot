import { useQuery } from '@tanstack/react-query';

import { listNodes } from '../api/nodes.api';

export function useNodesQuery() {
  return useQuery({
    queryKey: ['nodes'],
    queryFn: listNodes,
    refetchInterval: false, // DISABLED: Prevent GPU driver overload from frequent nvidia-smi calls
    staleTime: 30_000, // Cache for 30 seconds
    refetchOnWindowFocus: false,
  });
}
