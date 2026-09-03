interface RequestOptions {
  baseUrl: string
  accessToken: string
  organizationId: string
}

export class MarketSupplyApiError extends Error {
  readonly status: number
  readonly reasonCode: string | null

  constructor(status: number, reasonCode: string | null, detail?: string) {
    super(detail ?? `Requisição recusada (${status}).`)
    this.status = status
    this.reasonCode = reasonCode
  }
}

export interface MarketSupplyAggregateAssessmentRequest {
  policy_id: string
  policy_version: number
  purpose: string
  quantity: number
  commercial_window: {
    from: string
    until: string
  }
  reference_time: string
  knowledge_cutoff: string
  candidate_criteria: {
    subject_type: string
    required_tags: string[]
  }
}

export interface MarketSupplyGapSummary {
  code: string
  count: number
}

export interface MarketSupplyAggregatePayload {
  population_count: number
  readiness_counts: Record<string, number>
  ready_now: number
  conditioned: number
  indeterminate: number
  not_ready: number
  not_evaluated: number
  reassessment_required: number
  current_capacity: number
  requested_quantity: number | null
  estimated_shortage_now: number | null
  gap_summary: MarketSupplyGapSummary[]
  limitations: string[]
}

export interface MarketSupplyAggregateAssessmentResponse {
  status: 'RELEASED' | 'NOT_RELEASED'
  aggregate?: MarketSupplyAggregatePayload
}

export function assessMarketSupplyAggregate(
  options: RequestOptions,
  params: {
    request: MarketSupplyAggregateAssessmentRequest
    idempotencyKey: string
  },
): Promise<MarketSupplyAggregateAssessmentResponse> {
  return chamar<MarketSupplyAggregateAssessmentResponse>(
    '/v1/livestock/market-supply/aggregate-assessments',
    options,
    {
      method: 'POST',
      headers: {
        'Idempotency-Key': params.idempotencyKey,
      },
      body: JSON.stringify(params.request),
    },
  )
}

async function chamar<T>(
  path: string,
  { baseUrl, accessToken, organizationId }: RequestOptions,
  init: RequestInit,
): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'X-Titan-Organization-Id': organizationId,
      'Content-Type': 'application/json',
      ...init.headers,
    },
  })

  if (!response.ok) {
    const corpo = await response.json().catch(() => null)
    throw new MarketSupplyApiError(response.status, corpo?.reason_code ?? null, corpo?.detail)
  }

  return (await response.json()) as T
}
