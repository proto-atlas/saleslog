import { STATIC_DEMO_CLOCK_ISO } from '../demoMode'
import type {
  AgentApprovalDecision,
  AgentApprovalDecisionResponse,
  AgentApprovalOut,
  AgentArtifactOut,
  AgentRunCreate,
  AgentRunCreateResponse,
  AgentRunOut,
  AgentRunSourceOut,
  CustomerCreate,
  CustomerListItem,
  CustomerOut,
  CustomerPatch,
  CustomersListResponse,
  DashboardSummary,
  UserCreate,
  UserOut,
  UserPatch,
  UsersResponse,
  VisitCreate,
  VisitListItem,
  VisitOut,
  VisitPatch,
  VisitsListResponse,
} from './client'

const NOW = STATIC_DEMO_CLOCK_ISO
const TODAY_VISIT_AT = '2026-06-28T04:00:00.000Z'

let nextCustomerId = 6
let nextVisitId = 8
let nextUserId = 4
let nextRunId = 2
let nextApprovalId = 3
let nextArtifactId = 2
let nextSourceId = 4

let users: UsersResponse['items'] = [
  { id: 1, name: '高橋 誠', role: 'manager', linked: true },
  { id: 2, name: '佐藤 葵', role: 'sales', linked: true },
  { id: 3, name: '田中 健', role: 'sales', linked: false },
]

let customers: CustomerListItem[] = [
  {
    id: 1,
    name: '株式会社アオバ製作所',
    address: '東京都品川区北品川 2-4-8',
    area: 'tokyo',
    status: 'negotiating',
    owner_id: 1,
    created_at: '2026-04-01T00:00:00.000Z',
    updated_at: '2026-06-20T02:00:00.000Z',
    last_visited_at: '2026-06-24T01:30:00.000Z',
  },
  {
    id: 2,
    name: '東都メディカル株式会社',
    address: '東京都千代田区丸の内 1-3-2',
    area: 'tokyo',
    status: 'won',
    owner_id: 2,
    created_at: '2026-04-04T00:00:00.000Z',
    updated_at: '2026-06-18T05:30:00.000Z',
    last_visited_at: '2026-06-18T05:30:00.000Z',
  },
  {
    id: 3,
    name: '千葉ロジスティクス',
    address: '千葉県市川市塩浜 3-8-1',
    area: 'chiba',
    status: 'prospect',
    owner_id: 3,
    created_at: '2026-04-12T00:00:00.000Z',
    updated_at: '2026-06-15T06:00:00.000Z',
    last_visited_at: null,
  },
  {
    id: 4,
    name: '神奈川フードサービス',
    address: '神奈川県横浜市中区本町 4-11',
    area: 'kanagawa',
    status: 'dormant',
    owner_id: 2,
    created_at: '2026-05-02T00:00:00.000Z',
    updated_at: '2026-06-08T03:00:00.000Z',
    last_visited_at: '2026-05-29T03:00:00.000Z',
  },
  {
    id: 5,
    name: '埼玉精密機器',
    address: '埼玉県さいたま市大宮区桜木町 1-7',
    area: 'saitama',
    status: 'negotiating',
    owner_id: 1,
    created_at: '2026-05-14T00:00:00.000Z',
    updated_at: '2026-06-22T07:00:00.000Z',
    last_visited_at: '2026-06-21T07:00:00.000Z',
  },
]

let visits: VisitOut[] = [
  {
    id: 1,
    customer_id: 1,
    user_id: 1,
    activity_type: 'visit',
    status: 'done',
    visited_at: '2026-06-24T01:30:00.000Z',
    memo: '次回提案では現場担当者向けの導入手順を先に確認する。',
    created_at: '2026-06-24T02:00:00.000Z',
    updated_at: '2026-06-24T02:00:00.000Z',
  },
  {
    id: 2,
    customer_id: 1,
    user_id: 1,
    activity_type: 'call',
    status: 'planned',
    visited_at: TODAY_VISIT_AT,
    memo: '午前中に見積条件を確認する。',
    created_at: '2026-06-27T01:00:00.000Z',
    updated_at: '2026-06-27T01:00:00.000Z',
  },
  {
    id: 3,
    customer_id: 2,
    user_id: 2,
    activity_type: 'online',
    status: 'done',
    visited_at: '2026-06-18T05:30:00.000Z',
    memo: '月次レポートの配信時間を調整する。',
    created_at: '2026-06-18T06:00:00.000Z',
    updated_at: '2026-06-18T06:00:00.000Z',
  },
  {
    id: 4,
    customer_id: 3,
    user_id: 3,
    activity_type: 'email',
    status: 'planned',
    visited_at: '2026-06-20T04:00:00.000Z',
    memo: '初回資料送付後の反応を確認する。',
    created_at: '2026-06-19T04:00:00.000Z',
    updated_at: '2026-06-19T04:00:00.000Z',
  },
  {
    id: 5,
    customer_id: 4,
    user_id: 2,
    activity_type: 'call',
    status: 'done',
    visited_at: '2026-05-29T03:00:00.000Z',
    memo: '次回接点は7月上旬に再設定する。',
    created_at: '2026-05-29T03:30:00.000Z',
    updated_at: '2026-05-29T03:30:00.000Z',
  },
  {
    id: 6,
    customer_id: 5,
    user_id: 1,
    activity_type: 'visit',
    status: 'done',
    visited_at: '2026-06-21T07:00:00.000Z',
    memo: '比較表を使った説明が有効。次回は導入スケジュールを詰める。',
    created_at: '2026-06-21T07:30:00.000Z',
    updated_at: '2026-06-21T07:30:00.000Z',
  },
  {
    id: 7,
    customer_id: 5,
    user_id: 1,
    activity_type: 'visit',
    status: 'planned',
    visited_at: '2026-07-01T05:00:00.000Z',
    memo: '導入時期と稟議に必要な資料を確認する。',
    created_at: '2026-06-22T07:00:00.000Z',
    updated_at: '2026-06-22T07:00:00.000Z',
  },
]

let agentRuns: AgentRunOut[] = [buildAgentRun(1, 1, '次回商談の準備をしたい')]
let agentApprovals: AgentApprovalOut[] = buildAgentApprovals(1, 1)

let agentArtifacts: AgentArtifactOut[] = [
  {
    id: 1,
    run_id: 1,
    artifact_type: 'meeting_prep',
    content_json: {
      customer_summary: {
        text: '株式会社アオバ製作所は現在商談中です。直近の訪問では、導入手順と見積条件の確認が次回課題として残っています。',
      },
      meeting_brief: {
        text: '次回商談では、現場担当者が不安に感じている導入手順と、稟議に必要な見積条件を先に確認します。',
      },
      risks: [
        { title: '導入時期の未確定', description: '稟議時期がずれると次回提案の優先度が下がる可能性があります。' },
      ],
      opportunities: [
        { title: '比較表の反応が良い', description: '前回訪問で比較表への反応が良く、導入判断の材料として使えます。' },
      ],
      suggested_questions: [
        { title: '稟議に必要な資料', description: '見積以外に必要な資料と提出期限を確認します。' },
        { title: '現場担当者の不安点', description: '導入手順で説明を厚くする箇所を確認します。' },
      ],
      suggested_next_actions: [
        { title: '見積条件の確認', description: '商談後に金額条件と導入時期を整理します。' },
        { title: '商談メモの保存', description: '確認事項と次回提案内容を活動記録として残します。' },
      ],
      follow_up_email_draft: {
        subject: '株式会社アオバ製作所 次回ご提案資料の確認',
        body: '本日はお時間をいただきありがとうございました。\n導入手順と見積条件について、確認事項を整理して改めてご連絡します。',
      },
    },
    claims_json: [
      {
        claim_id: 'claim_001',
        text: '直近の訪問で導入手順と見積条件の確認が次回課題として残っています',
      },
      {
        claim_id: 'claim_002',
        text: '前回訪問では比較表への反応が良好でした',
      },
    ],
    citation_candidates_json: [],
    citations_json: [
      {
        citation_id: 'cit_001',
        claim_id: 'claim_001',
        source_type: 'activity',
        source_id: '1',
      },
      {
        citation_id: 'cit_002',
        claim_id: 'claim_002',
        source_type: 'activity',
        source_id: '6',
      },
    ],
    uncertainties_json: [
      { title: '稟議期限', description: '稟議の提出期限は未確認です。' },
    ],
    schema_version: 'agent_output_v1',
    created_at: NOW,
  },
]

let agentSources: AgentRunSourceOut[] = [
  {
    id: 1,
    run_id: 1,
    source_type: 'customer',
    source_id: '1',
    source_version: 'v1',
    source_checksum: 'demo-customer-1',
    chunk_id: null,
    label: '顧客: 株式会社アオバ製作所',
    char_start: 0,
    char_end: 80,
    offset_unit: 'char',
    source_excerpt: '顧客名: 株式会社アオバ製作所 / ステータス: 商談中 / エリア: 東京',
    source_excerpt_redacted_at: null,
    created_at: NOW,
    expires_at: '2026-07-28T09:00:00.000Z',
  },
  {
    id: 2,
    run_id: 1,
    source_type: 'activity',
    source_id: '1',
    source_version: 'v1',
    source_checksum: 'demo-visit-1',
    chunk_id: null,
    label: '活動ログ: 2026-06-24',
    char_start: 0,
    char_end: 120,
    offset_unit: 'char',
    source_excerpt: '次回提案では現場担当者向けの導入手順を先に確認する。',
    source_excerpt_redacted_at: null,
    created_at: NOW,
    expires_at: '2026-07-28T09:00:00.000Z',
  },
  {
    id: 3,
    run_id: 1,
    source_type: 'activity',
    source_id: '6',
    source_version: 'v1',
    source_checksum: 'demo-visit-6',
    chunk_id: null,
    label: '活動ログ: 2026-06-21',
    char_start: 0,
    char_end: 120,
    offset_unit: 'char',
    source_excerpt: '比較表を使った説明が有効。次回は導入スケジュールを詰める。',
    source_excerpt_redacted_at: null,
    created_at: NOW,
    expires_at: '2026-07-28T09:00:00.000Z',
  },
]

export function handleStaticDemoRequest(
  path: string,
  init?: RequestInit,
): Response | null {
  const method = init?.method ?? 'GET'
  const url = new URL(path, staticDemoOrigin())
  const pathname = url.pathname

  if (method === 'GET' && pathname === '/api/me') return json(me())
  if (method === 'GET' && pathname === '/api/users') return json({ items: users })
  if (method === 'POST' && pathname === '/api/users') return json(createUser(init), 201)
  if (method === 'PATCH' && /^\/api\/users\/\d+$/.test(pathname)) {
    return json(updateUser(Number(pathname.split('/').at(-1)), init))
  }

  if (method === 'GET' && pathname === '/api/dashboard/summary') {
    return json(buildDashboardSummary())
  }
  if (method === 'GET' && pathname === '/api/customers') {
    return json(listCustomers(url))
  }
  if (method === 'POST' && pathname === '/api/customers') return json(createCustomer(init), 201)
  if (method === 'GET' && /^\/api\/customers\/\d+$/.test(pathname)) {
    return customerResponse(Number(pathname.split('/').at(-1)))
  }
  if (method === 'PATCH' && /^\/api\/customers\/\d+$/.test(pathname)) {
    return json(updateCustomer(Number(pathname.split('/').at(-1)), init))
  }
  if (method === 'DELETE' && /^\/api\/customers\/\d+$/.test(pathname)) {
    customers = customers.filter((customer) => customer.id !== Number(pathname.split('/').at(-1)))
    return new Response(null, { status: 204 })
  }
  const customerVisitsMatch = pathname.match(/^\/api\/customers\/(\d+)\/visits$/)
  if (method === 'GET' && customerVisitsMatch !== null) {
    return json(listVisits(url, Number(customerVisitsMatch[1])))
  }

  if (method === 'GET' && pathname === '/api/visits') return json(listVisits(url))
  if (method === 'POST' && pathname === '/api/visits') return json(createVisit(init), 201)
  if (method === 'GET' && /^\/api\/visits\/\d+$/.test(pathname)) {
    return visitResponse(Number(pathname.split('/').at(-1)))
  }
  if (method === 'PATCH' && /^\/api\/visits\/\d+$/.test(pathname)) {
    return json(updateVisit(Number(pathname.split('/').at(-1)), init))
  }
  if (method === 'DELETE' && /^\/api\/visits\/\d+$/.test(pathname)) {
    visits = visits.filter((visit) => visit.id !== Number(pathname.split('/').at(-1)))
    return new Response(null, { status: 204 })
  }

  const createRunMatch = pathname.match(/^\/api\/customers\/(\d+)\/agent-runs$/)
  if (method === 'POST' && createRunMatch !== null) {
    return json(createAgentRun(Number(createRunMatch[1]), init), 202)
  }
  if (method === 'GET' && createRunMatch !== null) {
    return json(agentRuns.filter((run) => run.customer_id === Number(createRunMatch[1])))
  }
  if (method === 'GET' && /^\/api\/agent-runs\/\d+$/.test(pathname)) {
    return agentRunResponse(Number(pathname.split('/').at(-1)))
  }
  const runArtifactsMatch = pathname.match(/^\/api\/agent-runs\/(\d+)\/artifacts$/)
  if (method === 'GET' && runArtifactsMatch !== null) {
    return json(agentArtifacts.filter((artifact) => artifact.run_id === Number(runArtifactsMatch[1])))
  }
  const runSourcesMatch = pathname.match(/^\/api\/agent-runs\/(\d+)\/sources$/)
  if (method === 'GET' && runSourcesMatch !== null) {
    return json(agentSources.filter((source) => source.run_id === Number(runSourcesMatch[1])))
  }
  const runApprovalsMatch = pathname.match(/^\/api\/agent-runs\/(\d+)\/approvals$/)
  if (method === 'GET' && runApprovalsMatch !== null) {
    return json(agentApprovals.filter((approval) => approval.run_id === Number(runApprovalsMatch[1])))
  }
  const approvalMatch = pathname.match(/^\/api\/agent-runs\/(\d+)\/approvals\/(\d+)$/)
  if (method === 'PATCH' && approvalMatch !== null) {
    return json(editApproval(Number(approvalMatch[2]), init))
  }
  const approveMatch = pathname.match(/^\/api\/agent-runs\/(\d+)\/approvals\/(\d+)\/approve$/)
  if (method === 'POST' && approveMatch !== null) {
    return json(approveApproval(Number(approveMatch[1]), Number(approveMatch[2]), init))
  }
  const rejectMatch = pathname.match(/^\/api\/agent-runs\/(\d+)\/approvals\/(\d+)\/reject$/)
  if (method === 'POST' && rejectMatch !== null) {
    return json(rejectApproval(Number(rejectMatch[2])))
  }
  return null
}

export function handleStaticDemoTextRequest(path: string): string | null {
  const url = new URL(path, staticDemoOrigin())
  const runId = Number(url.pathname.match(/^\/api\/agent-runs\/(\d+)\/events$/)?.[1])
  if (!Number.isFinite(runId)) return null
  return [
    eventLine(1, 'run_created'),
    eventLine(2, 'customer_loaded'),
    eventLine(3, 'activities_loaded'),
    eventLine(4, 'knowledge_search_completed'),
    eventLine(5, 'drafting_completed'),
    eventLine(6, 'approval_required'),
    eventLine(7, 'waiting_for_approval'),
  ].join('')
}

function me(): UserOut {
  return { id: 1, name: '高橋 誠', role: 'manager', linked: true }
}

function listCustomers(url: URL): CustomersListResponse {
  const search = url.searchParams.get('search')?.trim().toLowerCase()
  const area = url.searchParams.get('area')
  const status = url.searchParams.get('status')
  const ownerId = numberParam(url, 'owner_id')
  const page = numberParam(url, 'page') ?? 1
  const pageSize = numberParam(url, 'page_size') ?? 10
  const sort = url.searchParams.get('sort') ?? '-updated_at'
  let items = customers.filter((customer) => {
    if (search !== undefined && search !== '' && !customer.name.toLowerCase().includes(search)) {
      return false
    }
    if (area !== null && customer.area !== area) return false
    if (status !== null && customer.status !== status) return false
    if (ownerId !== undefined && customer.owner_id !== ownerId) return false
    return true
  })
  items = sortCustomers(items, sort)
  return paginate(items, page, pageSize)
}

function listVisits(url: URL, customerId?: number): VisitsListResponse {
  const page = numberParam(url, 'page') ?? 1
  const pageSize = numberParam(url, 'page_size') ?? 10
  const filterCustomerId = customerId ?? numberParam(url, 'customer_id')
  const userId = numberParam(url, 'user_id')
  const status = url.searchParams.get('status')
  const unrecorded = url.searchParams.get('unrecorded') === 'true'
  const items = visits
    .filter((visit) => filterCustomerId === undefined || visit.customer_id === filterCustomerId)
    .filter((visit) => userId === undefined || visit.user_id === userId)
    .filter((visit) => status === null || visit.status === status)
    .filter((visit) => !unrecorded || (visit.status === 'planned' && visit.visited_at < NOW))
    .sort((a, b) => b.visited_at.localeCompare(a.visited_at))
    .map(toVisitListItem)
  return paginate(items, page, pageSize)
}

function buildDashboardSummary(): DashboardSummary {
  return {
    total_customers: customers.length,
    visits_this_month: visits.filter((visit) => visit.visited_at.startsWith('2026-06')).length,
    visits_trend: [
      { month: '2026-01', count: 4 },
      { month: '2026-02', count: 7 },
      { month: '2026-03', count: 9 },
      { month: '2026-04', count: 12 },
      { month: '2026-05', count: 10 },
      { month: '2026-06', count: visits.filter((visit) => visit.visited_at.startsWith('2026-06')).length },
    ],
    by_area: ['tokyo', 'kanagawa', 'saitama', 'chiba', 'other'].map((area) => ({
      area: area as DashboardSummary['by_area'][number]['area'],
      count: customers.filter((customer) => customer.area === area).length,
    })),
    by_owner: users
      .filter((user) => user.role !== null && user.role !== undefined)
      .map((user) => ({
        owner_id: user.id,
        owner_name: user.name,
        count: customers.filter((customer) => customer.owner_id === user.id).length,
      })),
    unrecorded_count: visits.filter(
      (visit) => visit.status === 'planned' && visit.visited_at < NOW,
    ).length,
    today_visits: visits
      .filter((visit) => visit.visited_at === TODAY_VISIT_AT)
      .map((visit) => ({
        visit_id: visit.id,
        customer_id: visit.customer_id,
        customer_name: customerName(visit.customer_id),
        owner_id: customerOwnerId(visit.customer_id),
        visited_at: visit.visited_at,
        status: visit.status,
      })),
  }
}

function createCustomer(init?: RequestInit): CustomerOut {
  const body = parseBody<CustomerCreate>(init)
  const customer: CustomerListItem = {
    id: nextCustomerId,
    name: body.name,
    address: body.address ?? null,
    area: body.area,
    status: body.status,
    owner_id: body.owner_id ?? me().id,
    created_at: NOW,
    updated_at: NOW,
    last_visited_at: null,
  }
  nextCustomerId += 1
  customers = [customer, ...customers]
  return toCustomerOut(customer)
}

function updateCustomer(id: number, init?: RequestInit): CustomerOut {
  const body = parseBody<CustomerPatch>(init)
  customers = customers.map((customer) =>
    customer.id === id ? applyCustomerPatch(customer, body) : customer,
  )
  return toCustomerOut(requiredCustomer(id))
}

function createVisit(init?: RequestInit): VisitOut {
  const body = parseBody<VisitCreate>(init)
  const visit: VisitOut = {
    id: nextVisitId,
    customer_id: body.customer_id,
    user_id: me().id,
    activity_type: body.activity_type,
    status: body.status,
    visited_at: body.visited_at,
    memo: body.memo ?? null,
    created_at: NOW,
    updated_at: NOW,
  }
  nextVisitId += 1
  visits = [visit, ...visits]
  refreshLastVisitedAt(visit.customer_id)
  return visit
}

function updateVisit(id: number, init?: RequestInit): VisitOut {
  const body = parseBody<VisitPatch>(init)
  visits = visits.map((visit) =>
    visit.id === id ? applyVisitPatch(visit, body) : visit,
  )
  const visit = requiredVisit(id)
  refreshLastVisitedAt(visit.customer_id)
  return visit
}

function createUser(init?: RequestInit): UserOut {
  const body = parseBody<UserCreate>(init)
  const user: UsersResponse['items'][number] = {
    id: nextUserId,
    name: body.name,
    role: body.role,
    linked: false,
  }
  nextUserId += 1
  users = [...users, user]
  return { id: user.id, name: user.name, role: user.role ?? 'sales', linked: user.linked }
}

function updateUser(id: number, init?: RequestInit): UserOut {
  const body = parseBody<UserPatch>(init)
  users = users.map((user) =>
    user.id === id ? applyUserPatch(user, body) : user,
  )
  const user = users.find((item) => item.id === id)
  if (user === undefined) throw new Error('user not found')
  return { id: user.id, name: user.name, role: user.role ?? 'sales', linked: user.linked }
}

function createAgentRun(customerId: number, init?: RequestInit): AgentRunCreateResponse {
  const body = parseBody<AgentRunCreate>(init)
  const run = buildAgentRun(nextRunId, customerId, body.objective, body.workflow_type)
  agentArtifacts = [buildAgentArtifact(nextArtifactId, run.id), ...agentArtifacts]
  nextArtifactId += 1
  const sources = buildAgentSources(run.id).map((source) => {
    const nextSource = { ...source, id: nextSourceId }
    nextSourceId += 1
    return nextSource
  })
  agentSources = [...sources, ...agentSources]
  const approvals = buildAgentApprovals(run.id, customerId).map((approval) => {
    const nextApproval = { ...approval, id: nextApprovalId }
    nextApprovalId += 1
    return nextApproval
  })
  agentApprovals = [...approvals, ...agentApprovals]
  agentRuns = [run, ...agentRuns]
  nextRunId += 1
  return { run_id: run.id, status: run.status, reused: false }
}

function editApproval(approvalId: number, init?: RequestInit): AgentApprovalOut {
  const body = parseBody<{ edited_payload_json: Record<string, unknown> }>(init)
  agentApprovals = agentApprovals.map((approval) =>
    approval.id === approvalId
      ? {
          ...approval,
          version: approval.version + 1,
          edited_payload_json: body.edited_payload_json,
          updated_at: NOW,
        }
      : approval,
  )
  return requiredApproval(approvalId)
}

function approveApproval(
  runId: number,
  approvalId: number,
  init?: RequestInit,
): AgentApprovalDecisionResponse {
  parseBody<AgentApprovalDecision>(init)
  const approval = requiredApproval(approvalId)
  const savedPayload = approval.edited_payload_json ?? approval.original_payload_json
  const nextApproval: AgentApprovalOut = {
    ...approval,
    status: approval.edited_payload_json === null ? 'persisted' : 'edited_and_approved',
    approved_payload_json: savedPayload,
    decided_by: me().id,
    decided_at: NOW,
    persisted_at: NOW,
    business_record_type: approval.action_type === 'email_draft' ? 'email_draft' : 'task',
    business_record_id: approval.id + 100,
    updated_at: NOW,
  }
  agentApprovals = agentApprovals.map((item) => (item.id === approvalId ? nextApproval : item))
  if (agentApprovals.filter((item) => item.run_id === runId).every((item) => item.status !== 'pending')) {
    agentRuns = agentRuns.map((run) =>
      run.id === runId ? { ...run, status: 'completed', completed_at: NOW, updated_at: NOW } : run,
    )
  }
  return {
    approval: {
      id: nextApproval.id,
      run_id: nextApproval.run_id,
      customer_id: nextApproval.customer_id,
      version: nextApproval.version,
      action_type: nextApproval.action_type,
      business_record_type: nextApproval.business_record_type,
      business_record_id: nextApproval.business_record_id,
      status: nextApproval.status,
    },
    status_code: 200,
    message_key: 'approval_persisted',
    retry_with_new_idempotency_key: false,
    requires_reconciliation: false,
  }
}

function rejectApproval(approvalId: number): AgentApprovalOut {
  agentApprovals = agentApprovals.map((approval) =>
    approval.id === approvalId
      ? { ...approval, status: 'rejected', decided_by: me().id, decided_at: NOW, updated_at: NOW }
      : approval,
  )
  return requiredApproval(approvalId)
}

function buildAgentRun(
  id: number,
  customerId: number,
  objective: string,
  workflowType: AgentRunOut['workflow_type'] = 'meeting_prep',
): AgentRunOut {
  return {
    id,
    user_id: 1,
    customer_id: customerId,
    workflow_type: workflowType,
    objective,
    status: 'waiting_for_approval',
    schema_version: 'agent_output_v1',
    workflow_version: 'agent_workflow_v1',
    prompt_version: 'agent_prompt_v1',
    provider: 'static-demo',
    model: 'demo-response',
    model_params_json: { temperature: 0 },
    started_at: NOW,
    completed_at: null,
    latency_ms: 240,
    last_error_code: null,
    last_error_message_safe: null,
    created_at: NOW,
    updated_at: NOW,
  }
}

function buildAgentArtifact(id: number, runId: number): AgentArtifactOut {
  const baseArtifact = agentArtifacts[0]
  return {
    ...baseArtifact,
    id,
    run_id: runId,
    created_at: NOW,
  }
}

function buildAgentSources(runId: number): AgentRunSourceOut[] {
  return agentSources
    .filter((source) => source.run_id === 1)
    .map((source) => ({
      ...source,
      run_id: runId,
      created_at: NOW,
    }))
}

function buildAgentApprovals(runId: number, customerId: number): AgentApprovalOut[] {
  return [
    {
      id: 1,
      run_id: runId,
      customer_id: customerId,
      version: 1,
      action_type: 'email_draft',
      target_entity_type: 'customer',
      target_entity_id: customerId,
      business_record_type: null,
      business_record_id: null,
      original_payload_json: {
        subject: '株式会社アオバ製作所 次回ご提案資料の確認',
        body: '本日はお時間をいただきありがとうございました。\n導入手順と見積条件について、確認事項を整理して改めてご連絡します。',
        claim_ids: ['claim_001'],
      },
      edited_payload_json: null,
      approved_payload_json: null,
      payload_schema_version: 'email_draft_v1',
      status: 'pending',
      decided_by: null,
      decided_at: null,
      persisted_at: null,
      persist_error: null,
      expires_at: '2026-07-28T09:00:00.000Z',
      created_at: NOW,
      updated_at: NOW,
    },
    {
      id: 2,
      run_id: runId,
      customer_id: customerId,
      version: 1,
      action_type: 'task',
      target_entity_type: 'customer',
      target_entity_id: customerId,
      business_record_type: null,
      business_record_id: null,
      original_payload_json: {
        title: '株式会社アオバ製作所 への次回フォロー',
        description: '商談後に確認事項と次回提案内容を整理する。',
        claim_ids: ['claim_001', 'claim_002'],
      },
      edited_payload_json: null,
      approved_payload_json: null,
      payload_schema_version: 'task_v1',
      status: 'pending',
      decided_by: null,
      decided_at: null,
      persisted_at: null,
      persist_error: null,
      expires_at: '2026-07-28T09:00:00.000Z',
      created_at: NOW,
      updated_at: NOW,
    },
  ]
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function eventLine(id: number, safeMessageKey: string): string {
  return `id: ${id}\nevent: agent_event\ndata: ${JSON.stringify({
    event_seq: id,
    event_type: safeMessageKey,
    safe_message_key: safeMessageKey,
  })}\n\n`
}

function paginate<T>(items: T[], page: number, pageSize: number) {
  const start = (page - 1) * pageSize
  return {
    items: items.slice(start, start + pageSize),
    total: items.length,
    page,
    page_size: pageSize,
  }
}

function parseBody<T>(init?: RequestInit): T {
  return init?.body === undefined ? ({} as T) : JSON.parse(String(init.body)) as T
}

function numberParam(url: URL, key: string): number | undefined {
  const value = url.searchParams.get(key)
  if (value === null || !/^\d+$/.test(value)) return undefined
  return Number(value)
}

function sortCustomers(items: CustomerListItem[], sort: string): CustomerListItem[] {
  const sorted = [...items]
  if (sort === 'name') return sorted.sort((a, b) => a.name.localeCompare(b.name, 'ja'))
  if (sort === '-name') return sorted.sort((a, b) => b.name.localeCompare(a.name, 'ja'))
  if (sort === 'created_at') return sorted.sort((a, b) => a.created_at.localeCompare(b.created_at))
  if (sort === '-created_at') return sorted.sort((a, b) => b.created_at.localeCompare(a.created_at))
  if (sort === 'updated_at') return sorted.sort((a, b) => a.updated_at.localeCompare(b.updated_at))
  return sorted.sort((a, b) => b.updated_at.localeCompare(a.updated_at))
}

function toCustomerOut(customer: CustomerListItem): CustomerOut {
  return {
    id: customer.id,
    name: customer.name,
    address: customer.address,
    area: customer.area,
    status: customer.status,
    owner_id: customer.owner_id,
    created_at: customer.created_at,
    updated_at: customer.updated_at,
  }
}

function applyCustomerPatch(
  customer: CustomerListItem,
  body: CustomerPatch,
): CustomerListItem {
  return {
    ...customer,
    name: body.name ?? customer.name,
    address: body.address ?? customer.address,
    area: body.area ?? customer.area,
    status: body.status ?? customer.status,
    owner_id: body.owner_id ?? customer.owner_id,
    updated_at: NOW,
  }
}

function applyVisitPatch(visit: VisitOut, body: VisitPatch): VisitOut {
  return {
    ...visit,
    activity_type: body.activity_type ?? visit.activity_type,
    status: body.status ?? visit.status,
    visited_at: body.visited_at ?? visit.visited_at,
    memo: body.memo ?? visit.memo,
    updated_at: NOW,
  }
}

function applyUserPatch(
  user: UsersResponse['items'][number],
  body: UserPatch,
): UsersResponse['items'][number] {
  return {
    ...user,
    name: body.name ?? user.name,
    role: body.role ?? user.role,
    linked:
      body.external_id === undefined ? user.linked : body.external_id !== null,
  }
}

function toVisitListItem(visit: VisitOut): VisitListItem {
  return {
    id: visit.id,
    customer_id: visit.customer_id,
    customer_name: customerName(visit.customer_id),
    owner_id: customerOwnerId(visit.customer_id),
    user_id: visit.user_id,
    user_name: userName(visit.user_id),
    activity_type: visit.activity_type,
    status: visit.status,
    visited_at: visit.visited_at,
    created_at: visit.created_at,
    updated_at: visit.updated_at,
  }
}

function customerResponse(id: number): Response {
  const customer = customers.find((item) => item.id === id)
  return customer === undefined ? json({ detail: 'Not Found' }, 404) : json(toCustomerOut(customer))
}

function visitResponse(id: number): Response {
  const visit = visits.find((item) => item.id === id)
  return visit === undefined ? json({ detail: 'Not Found' }, 404) : json(visit)
}

function agentRunResponse(id: number): Response {
  const run = agentRuns.find((item) => item.id === id)
  return run === undefined ? json({ detail: 'Not Found' }, 404) : json(run)
}

function requiredCustomer(id: number): CustomerListItem {
  const customer = customers.find((item) => item.id === id)
  if (customer === undefined) throw new Error('customer not found')
  return customer
}

function requiredVisit(id: number): VisitOut {
  const visit = visits.find((item) => item.id === id)
  if (visit === undefined) throw new Error('visit not found')
  return visit
}

function requiredApproval(id: number): AgentApprovalOut {
  const approval = agentApprovals.find((item) => item.id === id)
  if (approval === undefined) throw new Error('approval not found')
  return approval
}

function customerName(id: number): string {
  return customers.find((customer) => customer.id === id)?.name ?? `顧客 #${id}`
}

function customerOwnerId(id: number): number {
  return customers.find((customer) => customer.id === id)?.owner_id ?? me().id
}

function userName(id: number): string {
  return users.find((user) => user.id === id)?.name ?? `ユーザー #${id}`
}

function staticDemoOrigin(): string {
  return typeof window === 'undefined' ? 'http://localhost' : window.location.origin
}

function refreshLastVisitedAt(customerId: number): void {
  const lastVisit = visits
    .filter((visit) => visit.customer_id === customerId && visit.status === 'done')
    .sort((a, b) => b.visited_at.localeCompare(a.visited_at))[0]
  customers = customers.map((customer) =>
    customer.id === customerId
      ? { ...customer, last_visited_at: lastVisit?.visited_at ?? null, updated_at: NOW }
      : customer,
  )
}
