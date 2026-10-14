import { titanRequest, titanRequestBytes, type RequestOptions } from './client'

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
    population_snapshot_digest: string
    selection_criteria_digest: string
    commercial_window: {
      start: string | null
      end: string | null
    }
    limitations: string[]
  } | null
  limitations: string[]
}

export interface CommercialPassportGapRecommendation {
  action_code: string
  description: string
}

export interface CommercialPassportGap {
  opportunity_code: string
  opportunity_name: string
  dimension: string
  subject_scope: string
  gap_code: string
  label: string
  category: string
  reason: string
  reason_codes: string[]
  recommended_action: CommercialPassportGapRecommendation
  affected_count: number | null
  limitations: string[]
}

export interface CommercialPassportGapAnalysis {
  gap_count: number
  category_counts: Record<string, number>
  gaps: CommercialPassportGap[]
  limitations: string[]
}

export interface CommercialPassportEvidenceNeed {
  need_code: string
  opportunity_code: string
  opportunity_name: string
  evidence_type: string
  purpose: string
  subject_scope: string
  status: string
  source_gap_code: string | null
  expected_coverage: string
  recommended_action: string
  referenced_evidence_ids: string[]
  limitations: string[]
}

export interface CommercialPassportEvidenceVault {
  need_count: number
  missing_count: number
  status_counts: Record<string, number>
  needs: CommercialPassportEvidenceNeed[]
  limitations: string[]
}

export interface CommercialPassportResponse {
  property_id: string
  reference_time: string
  knowledge_cutoff: string
  evaluated_at: string
  result_boundary: string
  opportunities: CommercialPassportOpportunityAssessment[]
  gap_analysis: CommercialPassportGapAnalysis
  evidence_vault: CommercialPassportEvidenceVault
  limitations: string[]
}

export interface CommercialPassportIssuanceResponse {
  property_id: string
  dossier_id: string
  dossier_hash: string
  verification_bundle_id: string
  verification_manifest_digest: string
  issued_at: string
  audience: string
}

export interface VerificationBundleDownload {
  bytes: Uint8Array
  contentType: string
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

export function issuePropertyCommercialPassport(
  options: RequestOptions,
  params: {
    propertyId: string
    referenceTime: string
    knowledgeCutoff: string
    audience?: string
    idempotencyKey: string
  },
): Promise<CommercialPassportIssuanceResponse> {
  return chamar<CommercialPassportIssuanceResponse>(
    `/v1/livestock/properties/${params.propertyId}/commercial-passport/issue`,
    options,
    {
      method: 'POST',
      headers: { 'Idempotency-Key': params.idempotencyKey },
      body: JSON.stringify({
        reference_time: params.referenceTime,
        knowledge_cutoff: params.knowledgeCutoff,
        audience: params.audience ?? 'internal',
      }),
    },
  )
}

export async function downloadVerificationBundle(
  options: RequestOptions,
  bundleId: string,
): Promise<VerificationBundleDownload> {
  const response = await titanRequestBytes(
    `/v1/livestock/commercial-passport/verification-bundles/${bundleId}`,
    options,
    {},
    async (res) => {
      const corpo = await res.json().catch(() => null)
      return new CommercialPassportApiError(res.status, corpo?.reason_code ?? null, corpo?.detail)
    },
  )
  return {
    bytes: new Uint8Array(await response.arrayBuffer()),
    contentType: response.headers.get('Content-Type') ?? 'application/json',
  }
}

async function chamar<T>(path: string, options: RequestOptions, init: RequestInit = {}): Promise<T> {
  return titanRequest<T>(path, options, init, async (response) => {
    const corpo = await response.json().catch(() => null)
    return new CommercialPassportApiError(
      response.status,
      corpo?.reason_code ?? null,
      corpo?.detail,
    )
  })
}
