import { useQuery } from '@tanstack/react-query'

import { api, type DashboardSummary } from './client'

export const dashboardKeys = {
  all: ['dashboard'] as const,
  summary: () => ['dashboard', 'summary'] as const,
}

export function useDashboardSummary() {
  return useQuery({
    queryKey: dashboardKeys.summary(),
    queryFn: () => api.get<DashboardSummary>('/api/dashboard/summary'),
  })
}
