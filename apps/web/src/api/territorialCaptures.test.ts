import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  TerritorialCaptureApiError,
  criarPropriedadeQa,
  listarCapturasTerritoriais,
  registrarCapturaOverlapQa,
  registrarGeometriaQa,
} from './territorialCaptures'

const options = {
  baseUrl: 'http://127.0.0.1:8000',
  accessToken: 'meu-token',
  organizationId: 'org-1',
}

describe('territorialCaptures', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('cria propriedade QA com autenticação e OrganizationContext', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({ property_id: 'p1', code: 'TERR-QA-1', name: 'Fazenda' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await criarPropriedadeQa(options, 'TERR-QA-1')

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/v1/livestock/properties',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          Authorization: 'Bearer meu-token',
          'X-Titan-Organization-Id': 'org-1',
          'Content-Type': 'application/json',
        }),
      }),
    )
  })

  it('registra geometria declarada para a propriedade', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({ geometry_id: 'g1', property_id: 'p1', version: 1 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await registrarGeometriaQa(options, 'p1')

    const body = JSON.parse(String(fetchMock.mock.calls[0][1]?.body))
    expect(fetchMock.mock.calls[0][0]).toBe(
      'http://127.0.0.1:8000/v1/livestock/properties/p1/geometry',
    )
    expect(body.source).toBe('DECLARADA')
    expect(body.geojson.type).toBe('Polygon')
  })

  it('registra captura overlap sintética sem enviar digest controlado pelo cliente', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({ capture_id: 'c1', response_digest: 'digest' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await registrarCapturaOverlapQa(options, 'p1', 'g1', 1)

    const body = JSON.parse(String(fetchMock.mock.calls[0][1]?.body))
    expect(fetchMock.mock.calls[0][0]).toBe(
      'http://127.0.0.1:8000/v1/livestock/properties/p1/territorial-captures/synthetic',
    )
    expect(body.profile).toBe('FUNAI_LIKE_OVERLAP')
    expect(body.response_digest).toBeUndefined()
    expect(body.capture_id).toBeUndefined()
  })

  it('lista capturas territoriais sem payload bruto', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        items: [{ capture_id: 'c1', response_summary: {}, response_payload: undefined }],
        limit: 50,
        offset: 0,
        has_more: false,
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await listarCapturasTerritoriais(options, 'p1')

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/v1/livestock/properties/p1/territorial-captures?limit=50&offset=0',
      expect.anything(),
    )
  })

  it('lança erro tipado com reason_code', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 409,
        json: async () => ({
          reason_code: 'CONFLITO_DE_REFERENCIA',
          detail: 'geometry_version diverge.',
        }),
      }),
    )

    await expect(registrarCapturaOverlapQa(options, 'p1', 'g1', 999)).rejects.toMatchObject({
      status: 409,
      reasonCode: 'CONFLITO_DE_REFERENCIA',
    })
    await expect(registrarCapturaOverlapQa(options, 'p1', 'g1', 999)).rejects.toBeInstanceOf(
      TerritorialCaptureApiError,
    )
  })
})
