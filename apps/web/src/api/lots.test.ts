import { afterEach, describe, expect, it, vi } from 'vitest'
import { LotApiError, fetchLot, fetchLotMembers, fetchLots } from './lots'

const options = {
  baseUrl: 'http://127.0.0.1:8000',
  accessToken: 'meu-token',
  organizationId: 'org-1',
}

describe('lots', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('fetchLots envia Bearer e X-Titan-Organization-Id sem filtros', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [], limit: 50, offset: 0, has_more: false }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchLots(options)

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/v1/livestock/lots',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer meu-token',
          'X-Titan-Organization-Id': 'org-1',
        }),
      }),
    )
  })

  it('fetchLots monta a query string com limit/offset', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [], limit: 10, offset: 20, has_more: false }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchLots(options, { limit: 10, offset: 20 })

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/v1/livestock/lots?limit=10&offset=20',
      expect.anything(),
    )
  })

  it('fetchLot busca o detalhe pelo id', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ lot_id: 'l1', property_id: 'p1', code: 'L1', name: 'Lote 1' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchLot(options, 'l1')

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/v1/livestock/lots/l1',
      expect.anything(),
    )
  })

  it('fetchLotMembers busca os membros do lote', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ lot_id: 'l1', at_time: null, members: [] }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchLotMembers(options, 'l1')

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/v1/livestock/lots/l1/members',
      expect.anything(),
    )
  })

  it('lança LotApiError com o reason_code do corpo em respostas de erro', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        json: async () => ({
          reason_code: 'PERMISSAO_AUSENTE',
          detail: 'A operação exige a permissão LIVESTOCK_LOT.LER.',
        }),
      }),
    )

    await expect(fetchLots(options)).rejects.toMatchObject({
      status: 403,
      reasonCode: 'PERMISSAO_AUSENTE',
    })
    await expect(fetchLots(options)).rejects.toBeInstanceOf(LotApiError)
  })
})
