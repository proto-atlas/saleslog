import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  api,
  type AgentApprovalDecision,
  type AgentApprovalDecisionErrorResponse,
  type AgentApprovalDecisionResponse,
  type AgentApprovalOut,
  type AgentApprovalPatch,
  type AgentArtifactOut,
  type AgentRunCreate,
  type AgentRunCreateResponse,
  type AgentRunOut,
  type AgentRunSourceOut,
  type ApiResponse,
  type HTTPValidationError,
} from './client'
import { customersKeys } from './customers'
import { visitsKeys } from './visits'

export const agentKeys = {
  all: ['agent'] as const,
  customerRuns: (customerId: number) => ['agent', 'customer-runs', customerId] as const,
  run: (runId: number | undefined) => ['agent', 'run', runId ?? -1] as const,
  artifacts: (runId: number | undefined) =>
    ['agent', 'artifacts', runId ?? -1] as const,
  sources: (runId: number | undefined) =>
    ['agent', 'sources', runId ?? -1] as const,
  approvals: (runId: number | undefined) =>
    ['agent', 'approvals', runId ?? -1] as const,
  events: (runId: number | undefined, lastEventId: number) =>
    ['agent', 'events', runId ?? -1, lastEventId] as const,
}

export type AgentApprovalDecisionResult =
  | AgentApprovalDecisionResponse
  | AgentApprovalDecisionErrorResponse
  | HTTPValidationError
export type AgentApprovalDecisionHttpResult =
  ApiResponse<AgentApprovalDecisionResult>

export function isAgentApprovalDecisionSuccess(
  body: AgentApprovalDecisionResult,
): body is AgentApprovalDecisionResponse {
  return 'approval' in body
}

type AgentRunCreateResult = AgentRunCreateResponse & {
  id?: number
  reused?: boolean
}

export function useCreateAgentRun(customerId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: AgentRunCreate) =>
      api.post<AgentRunCreateResult>(`/api/customers/${customerId}/agent-runs`, body),
    onSuccess: (run) => {
      const runId = run.run_id ?? run.id
      void queryClient.invalidateQueries({ queryKey: agentKeys.customerRuns(customerId) })
      void queryClient.invalidateQueries({ queryKey: agentKeys.run(runId) })
      void queryClient.invalidateQueries({ queryKey: agentKeys.artifacts(runId) })
      void queryClient.invalidateQueries({ queryKey: agentKeys.approvals(runId) })
      void queryClient.invalidateQueries({ queryKey: agentKeys.sources(runId) })
    },
  })
}

export function useCustomerAgentRuns(customerId: number) {
  return useQuery({
    queryKey: agentKeys.customerRuns(customerId),
    queryFn: () => api.get<AgentRunOut[]>(`/api/customers/${customerId}/agent-runs`),
    refetchInterval: 1000,
  })
}

export function useAgentRun(runId: number | undefined) {
  return useQuery({
    queryKey: agentKeys.run(runId),
    queryFn: () => api.get<AgentRunOut>(`/api/agent-runs/${runId}`),
    enabled: runId !== undefined,
    refetchInterval: runId !== undefined ? 1000 : false,
  })
}

export function useAgentArtifacts(runId: number | undefined) {
  return useQuery({
    queryKey: agentKeys.artifacts(runId),
    queryFn: () => api.get<AgentArtifactOut[]>(`/api/agent-runs/${runId}/artifacts`),
    enabled: runId !== undefined,
    refetchInterval: runId !== undefined ? 1000 : false,
  })
}

export function useAgentSources(runId: number | undefined) {
  return useQuery({
    queryKey: agentKeys.sources(runId),
    queryFn: () => api.get<AgentRunSourceOut[]>(`/api/agent-runs/${runId}/sources`),
    enabled: runId !== undefined,
    refetchInterval: runId !== undefined ? 1000 : false,
  })
}

export function useAgentApprovals(runId: number | undefined) {
  return useQuery({
    queryKey: agentKeys.approvals(runId),
    queryFn: () => api.get<AgentApprovalOut[]>(`/api/agent-runs/${runId}/approvals`),
    enabled: runId !== undefined,
    refetchInterval: runId !== undefined ? 1000 : false,
  })
}

export function useAgentEvents(runId: number | undefined, lastEventId: number) {
  return useQuery({
    queryKey: agentKeys.events(runId, lastEventId),
    queryFn: () =>
      api.getText(`/api/agent-runs/${runId}/events`, {
        headers: { 'Last-Event-ID': String(lastEventId) },
      }),
    enabled: runId !== undefined,
    refetchInterval: runId !== undefined ? 1000 : false,
  })
}

export function useEditAgentApproval(runId: number, approvalId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: AgentApprovalPatch) =>
      api.patch<AgentApprovalOut>(
        `/api/agent-runs/${runId}/approvals/${approvalId}`,
        body,
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: agentKeys.approvals(runId) })
    },
  })
}

export function useApproveAgentApproval(runId: number, approvalId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: AgentApprovalDecision) =>
      api.postWithStatus<AgentApprovalDecisionResult>(
        `/api/agent-runs/${runId}/approvals/${approvalId}/approve`,
        body,
      ),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: agentKeys.run(runId) })
      void queryClient.invalidateQueries({ queryKey: agentKeys.approvals(runId) })
      if (isAgentApprovalDecisionSuccess(result.body)) {
        void queryClient.invalidateQueries({ queryKey: customersKeys.all })
        void queryClient.invalidateQueries({ queryKey: visitsKeys.all })
      }
    },
  })
}

export function useRejectAgentApproval(runId: number, approvalId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () =>
      api.post<AgentApprovalOut>(
        `/api/agent-runs/${runId}/approvals/${approvalId}/reject`,
        {},
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: agentKeys.run(runId) })
      void queryClient.invalidateQueries({ queryKey: agentKeys.approvals(runId) })
    },
  })
}
