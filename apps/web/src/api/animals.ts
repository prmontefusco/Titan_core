// Mesmo padrão de api/entityTypeRequests.ts: chamar<T>() central, erro tipado
// a partir de application/problem+json (ver apps/api/problem.py).

interface RequestOptions {
  baseUrl: string
  accessToken: string
  organizationId: string
}

export class AnimalApiError extends Error {
  readonly status: number
  readonly reasonCode: string | null

  constructor(status: number, reasonCode: string | null, detail?: string) {
    super(detail ?? `Requisição recusada (${status}).`)
    this.status = status
    this.reasonCode = reasonCode
  }
}

async function chamar<T>(path: string, { baseUrl, accessToken, organizationId }: RequestOptions): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'X-Titan-Organization-Id': organizationId,
    },
  })

  if (!response.ok) {
    const corpo = await response.json().catch(() => null)
    throw new AnimalApiError(response.status, corpo?.reason_code ?? null, corpo?.detail)
  }

  return (await response.json()) as T
}

export interface AnimalIdentifierResumo {
  identifier_id: string
  type: string
  value: string
  state: string
}

export interface SaidaResumo {
  exit_id: string
  exit_type: string
  occurred_at: string
  reason: string | null
  destination: string | null
  destination_counterparty_id: string | null
}

export interface AnimalResumo {
  animal_id: string
  sex: string
  breed: string | null
  birth_date: string | null
  birth_property_id: string | null
  birth_property_source: string
  birth_outcome: string
  identifiers: AnimalIdentifierResumo[]
  created_at: string
  saida: SaidaResumo | null
}

export interface Pagina<T> {
  items: T[]
  limit: number
  offset: number
  has_more: boolean
}

export interface PropriedadeResumo {
  property_id: string
  code: string
  name: string
  municipality: string
  state_code: string
  registration_number: string | null
  total_area_hectares: number | null
}

export interface LinhaDoTempoEntrada {
  occurred_at: string
  recorded_at: string
  entry_type: string
  source_kind: string
  aggregate_type: string
  aggregate_id: string
  superseded_by: string | null
}

export interface LinhaDoTempoResponse {
  animal_id: string
  known_until: string | null
  entry_count: number
  entries: LinhaDoTempoEntrada[]
}

export function fetchAnimals(
  options: RequestOptions,
  params: { identifier?: string; limit?: number; offset?: number } = {},
): Promise<Pagina<AnimalResumo>> {
  const query = new URLSearchParams()
  if (params.identifier) query.set('identifier', params.identifier)
  if (params.limit !== undefined) query.set('limit', String(params.limit))
  if (params.offset !== undefined) query.set('offset', String(params.offset))
  const suffix = query.toString() ? `?${query.toString()}` : ''
  return chamar<Pagina<AnimalResumo>>(`/v1/livestock/animals${suffix}`, options)
}

export function fetchAnimal(options: RequestOptions, animalId: string): Promise<AnimalResumo> {
  return chamar<AnimalResumo>(`/v1/livestock/animals/${animalId}`, options)
}

export function fetchProperty(options: RequestOptions, propertyId: string): Promise<PropriedadeResumo> {
  return chamar<PropriedadeResumo>(`/v1/livestock/properties/${propertyId}`, options)
}

export function fetchAnimalTimeline(
  options: RequestOptions,
  animalId: string,
): Promise<LinhaDoTempoResponse> {
  return chamar<LinhaDoTempoResponse>(`/v1/livestock/animals/${animalId}/timeline`, options)
}
