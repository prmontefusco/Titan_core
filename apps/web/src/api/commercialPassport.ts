import { titanRequest, type RequestOptions } from './client'

export class CommercialPassportApiError extends Error {
  readonly status: number
  readonly reasonCode: string | null

  constructor(status: number, reasonCode: string | null, detail?: string) {
    super(detail ?? `Requisição recusada (${status}).`)
    this.status = status
    this.reasonCode = reasonCode
  }
}

export interface CommercialPassportBreakdown {
  satisfied: number
  missing: number
  unknown: number
  failed: number
  not_applicable: number
  blocked: number
  applicable_count: number
  total_count: number
  derived_ratio: { satisfied: number; applicable: number } | null
}

export interface CommercialPassportRequirement {
  requirement_code: string
  label: string
  dimension: string
  status: string
  reason: string
  reason_codes: string[]
  limitations: string[]
}

export interface CommercialPassportOpportunityAssessment {
  opportunity: {
    code: string
    kind: string
    name: string
    purpose: string
    policy_id: string
    policy_version: number
  }
  property_readiness: {
    interpretation: string
    breakdown: CommercialPassportBreakdown
    requirements: CommercialPassportRequirement[]
  }
  population_eligibility: {
    subject_type: string
    counts_by_status: Record<string, number>
    total_count: number
    source_report_reference: string
    limitations: string[]
  } | null
  limitations: string[]
}

export interface CommercialPassportResponse {
  property_id: string
  reference_time: string
  knowledge_cutoff: string
  evaluated_at: string
  result_boundary: string
  opportunities: CommercialPassportOpportunityAssessment[]
  limitations: string[]
}

export function fetchPropertyCommercialPassport(
  options: RequestOptions,
  params: {
    propertyId: string
    referenceTime: string
    knowledgeCutoff: string
  },
): Promise<CommercialPassportResponse> {
  const query = new URLSearchParams({
    reference_time: params.referenceTime,
    knowledge_cutoff: params.knowledgeCutoff,
  })
  return chamar<CommercialPassportResponse>(
    `/v1/livestock/properties/${params.propertyId}/commercial-passport?${query.toString()}`,
    options,
  )
}

async function chamar<T>(path: string, options: RequestOptions): Promise<T> {
  return titanRequest<T>(path, options, {}, async (response) => {
    const corpo = await response.json().catch(() => null)
    return new CommercialPassportApiError(
      response.status,
      corpo?.reason_code ?? null,
      corpo?.detail,
    )
  })
}
