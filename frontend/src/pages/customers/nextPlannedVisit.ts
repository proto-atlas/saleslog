import type { VisitOut } from '../../api/client'

import { startOfJstDayMs } from '../../lib/dates'

type VisitSchedule = Pick<VisitOut, 'status' | 'visited_at'>

export function findNextPlannedVisit<T extends VisitSchedule>(
  visits: readonly T[],
  referenceTimeMs: number,
): T | null {
  const dayStartMs = startOfJstDayMs(referenceTimeMs)
  const upcomingVisits = visits.filter(
    (visit) =>
      visit.status === 'planned' &&
      new Date(visit.visited_at).getTime() >= dayStartMs,
  )
  if (upcomingVisits.length === 0) return null

  return upcomingVisits.reduce((nearest, visit) =>
    new Date(visit.visited_at) < new Date(nearest.visited_at) ? visit : nearest,
  )
}
