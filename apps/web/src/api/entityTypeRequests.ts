export const ENTITY_KINDS = [
  'ADMIN',
  'PRODUTOR',
  'FRIGORIFICO',
  'VETERINARIO',
  'AUDITOR',
  'CERTIFICADOR',
  'CONSUMIDOR',
] as const

export type EntityKind = (typeof ENTITY_KINDS)[number]

// O Keycloak devolve a claim como texto livre do perfil de registro — nunca
// como Membership ou Role (ADR-0031). Validar contra o mesmo catálogo do
// pedido real evita passar adiante um valor que o backend recusaria.
export function parseEntityKindClaim(value: unknown): EntityKind | undefined {
  return typeof value === 'string' && (ENTITY_KINDS as readonly string[]).includes(value)
    ? (value as EntityKind)
    : undefined
}

export type EntityTypeRequestStatusValue = 'PENDENTE' | 'APROVADA' | 'NEGADA'

export interface EntityTypeRequestSummary {
  request_id: string
  organization_id: string
  requested_kind: EntityKind
  status: EntityTypeRequestStatusValue
  requested_at: string
  decided_at: string | null
  decision_reason: string | null
}

export interface MyStatusResponse {
  has_membership: boolean
  requests: EntityTypeRequestSummary[]
}

// Espelha apps/api/problem.py: toda resposta de erro do Titan é
// application/problem+json com reason_code estável — é nele que a UI decide
// a mensagem, nunca no texto livre de detail.
export class EntityTypeRequestApiError extends Error {
  readonly status: number
  readonly reasonCode: string | null

  constructor(status: number, reasonCode: string | null, detail?: string) {
    super(detail ?? `Requisição recusada (${status}).`)
    this.status = status
    this.reasonCode = reasonCode
  }
}

interface RequestOptions {
  baseUrl: string
  accessToken: string
  organizationId: string
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
    throw new EntityTypeRequestApiError(
      response.status,
      corpo?.reason_code ?? null,
      corpo?.detail,
    )
  }

  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

export function fetchMyStatus(options: RequestOptions): Promise<MyStatusResponse> {
  return chamar<MyStatusResponse>('/v1/livestock/entity-type-requests/mine', options)
}

export function submitEntityTypeRequest(
  options: RequestOptions,
  requestedKind: EntityKind,
): Promise<EntityTypeRequestSummary> {
  return chamar<EntityTypeRequestSummary>('/v1/livestock/entity-type-requests', options, {
    method: 'POST',
    body: JSON.stringify({
      organization_id: options.organizationId,
      requested_kind: requestedKind,
    }),
  })
}

export function listPendingRequests(
  options: RequestOptions,
): Promise<EntityTypeRequestSummary[]> {
  return chamar<EntityTypeRequestSummary[]>('/v1/livestock/entity-type-requests', options)
}

export function approveRequest(
  options: RequestOptions,
  requestId: string,
): Promise<EntityTypeRequestSummary> {
  return chamar<EntityTypeRequestSummary>(
    `/v1/livestock/entity-type-requests/${requestId}/approve`,
    options,
    { method: 'POST' },
  )
}

export function denyRequest(
  options: RequestOptions,
  requestId: string,
  reason: string,
): Promise<EntityTypeRequestSummary> {
  return chamar<EntityTypeRequestSummary>(
    `/v1/livestock/entity-type-requests/${requestId}/deny`,
    options,
    { method: 'POST', body: JSON.stringify({ reason }) },
  )
}
