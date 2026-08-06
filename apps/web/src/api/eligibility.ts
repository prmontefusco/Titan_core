// Mesmo padrão de api/animals.ts, api/treatments.ts e api/entityTypeRequests.ts:
// chamar<T>() central, erro tipado a partir de application/problem+json.
//
// Diferença deste módulo: quando a decisão automática é recusada, o backend
// devolve 409 REVISAO_HUMANA_NECESSARIA com campos extras no nível raiz do
// corpo (proposal_id, evaluation_outcome, knowledge_limitations...) -- por
// isso EligibilityApiError guarda o corpo inteiro, não só reason_code/detail.

interface RequestOptions {
  baseUrl: string
  accessToken: string
  organizationId: string
}

export class EligibilityApiError extends Error {
  readonly status: number
  readonly reasonCode: string | null
  readonly body: Record<string, unknown> | null

  constructor(status: number, body: Record<string, unknown> | null) {
    super(typeof body?.detail === 'string' ? body.detail : `Requisição recusada (${status}).`)
    this.status = status
    this.reasonCode = typeof body?.reason_code === 'string' ? body.reason_code : null
    this.body = body
  }

  get requiresHumanReview(): boolean {
    return this.status === 409 && this.reasonCode === 'REVISAO_HUMANA_NECESSARIA'
  }

  get proposalId(): string | null {
    const valor = this.body?.proposal_id
    return typeof valor === 'string' ? valor : null
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
    throw new EligibilityApiError(response.status, corpo)
  }

  return (await response.json()) as T
}

export interface ElegibilidadeResponse {
  animal_id: string
  result: string
  outcome: string
  evaluation_id: string
  knowledge_cutoff: string
  knowledge_limitations: string[]
  decision_id: string
  dossier_id: string
  reasons: string[]
  governed_rule: Record<string, string> | null
}

export interface MarketDependencySummary {
  subject_key: string
  subject_label: string
  selected_subject_id: string | null
}

export interface MarketGap {
  code: string
  message: string
}

export interface MarketReason {
  code: string
  message: string
}

export interface MarketEntry {
  market: string
  status: string
  projection_status: string
  summary?: string
  dependency: MarketDependencySummary | null
  gaps: MarketGap[]
  reasons: MarketReason[]
  [chave: string]: unknown
}

export interface AvaliacaoMercadosResponse {
  animal_id: string
  requested_markets: string[]
  commercial_outlook: string
  can_sell_to_any_requested_market: boolean
  executive_summary: string
  eligible_markets: string[]
  blocked_markets: string[]
  conditioned_markets: string[]
  indeterminate_markets: string[]
  missing_markets: string[]
  required_subjects: Record<string, string>[]
  market_gaps: MarketGap[]
  evaluation_id: string
  decision_id: string
  dossier_id: string
  markets: MarketEntry[]
}

export interface ExplicacaoMercadoResponse {
  market: string
  status: string
  summary: string
  why: string[]
  next_action: string | null
  affected_animal_ids: string[]
}

export interface ExplicacaoComercialResponse {
  subject_type: string
  subject_id: string
  requested_markets: string[]
  commercial_outlook: string
  can_sell_to_any_requested_market: boolean
  executive_summary: string
  narrative: string
  recommended_next_action: string | null
  markets: ExplicacaoMercadoResponse[]
}

export interface LotMarketAnimalEntry {
  animal_id: string
  market: string
  status: string
  summary?: string
  [chave: string]: unknown
}

export interface LotMarketEntry {
  market: string
  status: string
  summary?: string
  dependency: MarketDependencySummary | null
  eligible_animal_ids: string[]
  blocked_animal_ids: string[]
  conditioned_animal_ids: string[]
  indeterminate_animal_ids: string[]
  missing_animal_ids: string[]
  animals: LotMarketAnimalEntry[]
  [chave: string]: unknown
}

export interface AvaliacaoMercadosLoteResponse {
  lot_id: string
  member_count: number
  requested_markets: string[]
  commercial_outlook: string
  can_sell_to_any_requested_market: boolean
  executive_summary: string
  eligible_markets: string[]
  blocked_markets: string[]
  conditioned_markets: string[]
  indeterminate_markets: string[]
  missing_markets: string[]
  required_subjects: Record<string, string>[]
  market_gaps: MarketGap[]
  markets: LotMarketEntry[]
}

export interface ContraparteExternaResumo {
  counterparty_id: string
  name: string
  counterparty_type: string
  identifiers: string[]
  notes: string | null
  created_at: string
}

interface Pagina<T> {
  items: T[]
  limit: number
  offset: number
  has_more: boolean
}

export function runAnimalEligibility(
  options: RequestOptions,
  animalId: string,
): Promise<ElegibilidadeResponse> {
  return chamar<ElegibilidadeResponse>(`/v1/livestock/animals/${animalId}/eligibility`, options, {
    method: 'POST',
  })
}

export function runMarketEvaluation(
  options: RequestOptions,
  params: { animalId: string; slaughterhouseCounterpartyId?: string },
): Promise<AvaliacaoMercadosResponse> {
  return chamar<AvaliacaoMercadosResponse>('/v1/livestock/market-eligibility/evaluations', options, {
    method: 'POST',
    body: JSON.stringify({
      animal_id: params.animalId,
      slaughterhouse_counterparty_id: params.slaughterhouseCounterpartyId ?? null,
    }),
  })
}

type SujeitoComercial =
  | { animalId: string; lotId?: undefined; slaughterhouseCounterpartyId?: string }
  | { lotId: string; animalId?: undefined; slaughterhouseCounterpartyId?: string }

export function runCommercialExplanation(
  options: RequestOptions,
  params: SujeitoComercial,
): Promise<ExplicacaoComercialResponse> {
  return chamar<ExplicacaoComercialResponse>(
    '/v1/livestock/market-eligibility/commercial-explanations',
    options,
    {
      method: 'POST',
      body: JSON.stringify({
        animal_id: params.animalId ?? null,
        lot_id: params.lotId ?? null,
        slaughterhouse_counterparty_id: params.slaughterhouseCounterpartyId ?? null,
      }),
    },
  )
}

export function runLotMarketEvaluation(
  options: RequestOptions,
  params: { lotId: string; slaughterhouseCounterpartyId?: string },
): Promise<AvaliacaoMercadosLoteResponse> {
  return chamar<AvaliacaoMercadosLoteResponse>(
    '/v1/livestock/market-eligibility/lots/evaluations',
    options,
    {
      method: 'POST',
      body: JSON.stringify({
        lot_id: params.lotId,
        slaughterhouse_counterparty_id: params.slaughterhouseCounterpartyId ?? null,
      }),
    },
  )
}

export function fetchExternalCounterparties(
  options: RequestOptions,
): Promise<Pagina<ContraparteExternaResumo>> {
  return chamar<Pagina<ContraparteExternaResumo>>('/v1/livestock/external-counterparties', options)
}
