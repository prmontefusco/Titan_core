import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  EntityTypeRequestApiError,
  fetchMyStatus,
  parseEntityKindClaim,
  submitEntityTypeRequest,
} from './entityTypeRequests'

const options = {
  baseUrl: 'http://127.0.0.1:8000',
  accessToken: 'meu-token',
  organizationId: 'org-1',
}

describe('entityTypeRequests', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('fetchMyStatus envia Bearer e X-Titan-Organization-Id', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ has_membership: false, requests: [] }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const resultado = await fetchMyStatus(options)

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/v1/livestock/entity-type-requests/mine',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer meu-token',
          'X-Titan-Organization-Id': 'org-1',
        }),
      }),
    )
    expect(resultado).toEqual({ has_membership: false, requests: [] })
  })

  it('submitEntityTypeRequest envia o corpo com organization_id e requested_kind', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({ request_id: 'r1', status: 'PENDENTE' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await submitEntityTypeRequest(options, 'PRODUTOR')

    const chamada = fetchMock.mock.calls[0]
    expect(chamada[0]).toBe('http://127.0.0.1:8000/v1/livestock/entity-type-requests')
    expect(chamada[1].method).toBe('POST')
    expect(JSON.parse(chamada[1].body)).toEqual({
      organization_id: 'org-1',
      requested_kind: 'PRODUTOR',
    })
  })

  it('lança EntityTypeRequestApiError com o reason_code do corpo', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 409,
        json: async () => ({ reason_code: 'PEDIDO_PENDENTE_JA_EXISTE', detail: 'já existe' }),
      }),
    )

    await expect(submitEntityTypeRequest(options, 'AUDITOR')).rejects.toMatchObject({
      status: 409,
      reasonCode: 'PEDIDO_PENDENTE_JA_EXISTE',
    })
    await expect(submitEntityTypeRequest(options, 'AUDITOR')).rejects.toBeInstanceOf(
      EntityTypeRequestApiError,
    )
  })

  it('parseEntityKindClaim aceita só valores do catálogo', () => {
    expect(parseEntityKindClaim('VETERINARIO')).toBe('VETERINARIO')
    expect(parseEntityKindClaim('ALGO_INVENTADO')).toBeUndefined()
    expect(parseEntityKindClaim(undefined)).toBeUndefined()
    expect(parseEntityKindClaim(42)).toBeUndefined()
  })
})
