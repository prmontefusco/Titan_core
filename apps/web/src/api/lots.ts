// Mesmo padrão de api/animals.ts, api/treatments.ts e api/eligibility.ts:
// chamar<T>() central, erro tipado a partir de application/problem+json.

import { titanRequest, type RequestOptions } from './client'

export class LotApiError extends Error {
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
  options: RequestOptions,
): Promise<T> {
  return titanRequest<T>(path, options, {}, async (response) => {
    const corpo = await response.json().catch(() => null)
    return new LotApiError(response.status, corpo?.reason_code ?? null, corpo?.detail)
  })
}

export interface LoteAnimaisResumo {
  lot_id: string
  property_id: string
  code: string
  name: string
  lot_type: string
  status: string
}

export interface Pagina<T> {
  items: T[]
  limit: number
  offset: number
  has_more: boolean
}

export interface LotMembership {
  membership_id: string
  animal_id: string
  valid_from: string
  valid_until: string | null
  reason: string
}

export interface LotMembersResponse {
  lot_id: string
  at_time: string | null
  members: LotMembership[]
}

export function fetchLots(
  options: RequestOptions,
  params: { limit?: number; offset?: number } = {},
): Promise<Pagina<LoteAnimaisResumo>> {
  const query = new URLSearchParams()
  if (params.limit !== undefined) query.set('limit', String(params.limit))
  if (params.offset !== undefined) query.set('offset', String(params.offset))
  const suffix = query.toString() ? `?${query.toString()}` : ''
  return chamar<Pagina<LoteAnimaisResumo>>(`/v1/livestock/lots${suffix}`, options)
}

export function fetchLot(options: RequestOptions, lotId: string): Promise<LoteAnimaisResumo> {
  return chamar<LoteAnimaisResumo>(`/v1/livestock/lots/${lotId}`, options)
}

export function fetchLotMembers(
  options: RequestOptions,
  lotId: string,
): Promise<LotMembersResponse> {
  return chamar<LotMembersResponse>(`/v1/livestock/lots/${lotId}/members`, options)
}
