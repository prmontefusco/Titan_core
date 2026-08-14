// Cliente técnico do T-05D Corte 5A: consome somente a API sintética já
// aprovada no Corte 4. Não interpreta conformidade e não cria decisão.

interface RequestOptions {
  baseUrl: string
  accessToken: string
  organizationId: string
}

export class TerritorialCaptureApiError extends Error {
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
    throw new TerritorialCaptureApiError(
      response.status,
      corpo?.reason_code ?? null,
      corpo?.detail,
    )
  }

  return (await response.json()) as T
}

export interface PropriedadeCriada {
  property_id: string
  code: string
  name: string
}

export interface GeometriaCriada {
  geometry_id: string
  property_id: string
  source: string
  layer: string
  srid: number
  source_digest: string
  external_reference: string | null
  version: number
  captured_at: string | null
  imported_at: string
}

export interface CapturaTerritorial {
  capture_id: string
  property_id: string
  geometry_id: string
  geometry_version: number
  source_profile_code: string
  source_environment: string
  source_layer: string
  operation: string
  request_scope_digest: string
  response_schema: string
  response_schema_version: number
  canonicalization_version: string
  response_digest: string
  response_summary: Record<string, unknown>
  source_version_ids: string[]
  source_valid_from: string | null
  source_valid_to: string | null
  captured_at: string
  known_at: string
  recorded_at: string
  limitations: string[]
}

export interface Pagina<T> {
  items: T[]
  limit: number
  offset: number
  has_more: boolean
}

const QUADRADO_MT = {
  type: 'Polygon',
  coordinates: [
    [
      [-56.1, -15.8],
      [-56.0, -15.8],
      [-56.0, -15.7],
      [-56.1, -15.7],
      [-56.1, -15.8],
    ],
  ],
}

export function criarPropriedadeQa(
  options: RequestOptions,
  codigo: string,
): Promise<PropriedadeCriada> {
  return chamar<PropriedadeCriada>('/v1/livestock/properties', options, {
    method: 'POST',
    body: JSON.stringify({
      code: codigo,
      name: 'Fazenda QA Territorial Sintetica',
      municipality: 'Cuiaba',
      state_code: 'MT',
    }),
  })
}

export function registrarGeometriaQa(
  options: RequestOptions,
  propertyId: string,
): Promise<GeometriaCriada> {
  return chamar<GeometriaCriada>(`/v1/livestock/properties/${propertyId}/geometry`, options, {
    method: 'POST',
    body: JSON.stringify({
      source: 'DECLARADA',
      geojson: QUADRADO_MT,
    }),
  })
}

export function registrarCapturaOverlapQa(
  options: RequestOptions,
  propertyId: string,
  geometryId: string,
  geometryVersion: number,
): Promise<CapturaTerritorial> {
  return chamar<CapturaTerritorial>(
    `/v1/livestock/properties/${propertyId}/territorial-captures/synthetic`,
    options,
    {
      method: 'POST',
      body: JSON.stringify({
        geometry_id: geometryId,
        geometry_version: geometryVersion,
        profile: 'FUNAI_LIKE_OVERLAP',
        request_scope: {
          geometry_id: geometryId,
          geometry_version: geometryVersion,
          layer: 'FUNAI_LIKE',
          operation: 'OVERLAP',
        },
        response_payload: {
          feature_count: 1,
          property_area_hectares: 1000,
          overlap_area_hectares: 42,
          source_version_ids: ['FUNAI_TEST_2026_V1'],
        },
        captured_at: '2026-03-01T00:00:00Z',
        known_at: '2026-03-02T00:00:00Z',
      }),
    },
  )
}

export function registrarCapturaTimelineQa(
  options: RequestOptions,
  propertyId: string,
  geometryId: string,
  geometryVersion: number,
): Promise<CapturaTerritorial> {
  return chamar<CapturaTerritorial>(
    `/v1/livestock/properties/${propertyId}/territorial-captures/synthetic`,
    options,
    {
      method: 'POST',
      body: JSON.stringify({
        geometry_id: geometryId,
        geometry_version: geometryVersion,
        profile: 'PRODES_LIKE_TIMELINE',
        request_scope: {
          layer: 'PRODES_LIKE',
          operation: 'TIMELINE',
        },
        response_payload: {
          property_area_hectares: 1000,
          years: [
            {
              year: 2024,
              feature_count: 1,
              source_area_hectares: 12.5,
              overlap_area_hectares: 4.2,
              source_version_ids: ['PRODES_TEST_2024_V1'],
            },
          ],
        },
        captured_at: '2026-03-01T00:00:00Z',
        known_at: '2026-03-02T00:00:00Z',
        source_valid_from: '2024-01-01T00:00:00Z',
        source_valid_to: '2025-01-01T00:00:00Z',
      }),
    },
  )
}

export function listarCapturasTerritoriais(
  options: RequestOptions,
  propertyId: string,
): Promise<Pagina<CapturaTerritorial>> {
  return chamar<Pagina<CapturaTerritorial>>(
    `/v1/livestock/properties/${propertyId}/territorial-captures?limit=50&offset=0`,
    options,
  )
}
