import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  CommercialPassportApiError,
  fetchPropertyCommercialPassport,
} from './commercialPassport'

const options = {
  baseUrl: 'http://127.0.0.1:8000',
  accessToken: 'meu-token',
  organizationId: 'org-1',
}

describe('commercialPassport', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('consulta o passaporte comercial com tenant e coordenadas temporais', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ property_id: 'p1', opportunities: [] }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchPropertyCommercialPassport(options, {
      propertyId: 'p1',
      referenceTime: '2026-09-11T00:00:00Z',
      knowledgeCutoff: '2026-09-11T00:00:00Z',
    })

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/v1/livestock/properties/p1/commercial-passport?reference_time=2026-09-11T00%3A00%3A00Z&knowledge_cutoff=2026-09-11T00%3A00%3A00Z',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer meu-token',
          'X-Titan-Organization-Id': 'org-1',
        }),
      }),
    )
  })

  it('lança erro tipado com reason_code', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        json: async () => ({
          reason_code: 'COMMERCIAL_PASSPORT_PIPELINE_NAO_HABILITADO',
          detail: 'pipeline interna desligada',
        }),
      }),
    )

    let erro: unknown
    try {
      await fetchPropertyCommercialPassport(options, {
        propertyId: 'p1',
        referenceTime: '2026-09-11T00:00:00Z',
        knowledgeCutoff: '2026-09-11T00:00:00Z',
      })
    } catch (error) {
      erro = error
    }

    expect(erro).toBeInstanceOf(CommercialPassportApiError)
    expect(erro).toMatchObject({
      status: 503,
      reasonCode: 'COMMERCIAL_PASSPORT_PIPELINE_NAO_HABILITADO',
    })
  })
})
