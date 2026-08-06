// Mesmo padrão de api/entityTypeRequests.ts: os erros deste fluxo (proposta não
// encontrada, autoridade de decisão ausente) não carregam campos extras como os
// de api/eligibility.ts -- reason_code/detail bastam.

interface RequestOptions {
  baseUrl: string
  accessToken: string
  organizationId: string
}

export class DecisionReviewApiError extends Error {
  readonly status: number
  readonly reasonCode: string | null

  constructor(status: number, reasonCode: string | null, detail?: string) {
    super(detail ?? `Requisição recusada (${status}).`)
    this.status = status
    this.reasonCode = reasonCode
  }
}

async function chamar<T>(
  path: string,
  { baseUrl, accessToken, organizationId }: RequestOptions,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'X-Titan-Organization-Id': organizationId,
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...init.headers,
    },
  })

  if (!response.ok) {
    const corpo = await response.json().catch(() => null)
    throw new DecisionReviewApiError(response.status, corpo?.reason_code ?? null, corpo?.detail)
  }

  return (await response.json()) as T
}

export interface DecisionProposalReason {
  code?: string
  message?: string
  [chave: string]: unknown
}

export interface DecisionProposalResponse {
  proposal_id: string
  evaluation_id: string
  evaluation_hash: string
  purpose: string
  proposed_result: string
  proposed_reasons: DecisionProposalReason[]
  justification_required: boolean
  created_at: string
  review_count: number
  current_proposal: boolean
}

export type ReviewConclusion = 'APROVA' | 'REJEITA' | 'DEVOLVE'

export interface DecisionReviewExecutionResponse {
  proposal_id: string
  review_id: string
  workflow_status: string
  decision_id: string | null
  dossier_id: string | null
}

export interface DossierResponse {
  dossier_id: string
  organization_id: string
  subject_reference: Record<string, unknown>
  purpose: string
  decision_id: string
  evaluation_id: string
  generated_at: string
  serialization_version: string
  document_version: number
  dossier_hash: string
  document: Record<string, unknown>
}

export function fetchProposal(
  options: RequestOptions,
  proposalId: string,
): Promise<DecisionProposalResponse> {
  return chamar<DecisionProposalResponse>(
    `/v1/livestock/decision-proposals/${proposalId}`,
    options,
  )
}

export function submitReview(
  options: RequestOptions,
  proposalId: string,
  params: { conclusion: ReviewConclusion; reasoning: string },
): Promise<DecisionReviewExecutionResponse> {
  return chamar<DecisionReviewExecutionResponse>(
    `/v1/livestock/decision-proposals/${proposalId}/reviews`,
    options,
    {
      method: 'POST',
      body: JSON.stringify({
        conclusion: params.conclusion,
        reasoning: params.reasoning,
      }),
    },
  )
}

export function fetchDossier(options: RequestOptions, dossierId: string): Promise<DossierResponse> {
  return chamar<DossierResponse>(`/v1/livestock/dossiers/${dossierId}`, options)
}
