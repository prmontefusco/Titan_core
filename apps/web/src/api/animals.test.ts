import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  AnimalApiError,
  fetchAnimal,
  fetchAnimalTimeline,
  fetchAnimals,
  fetchProperty,
} from './animals'

const options = {
  baseUrl: 'http://127.0.0.1:8000',
  accessToken: 'meu-token',
  organizationId: 'org-1',
}

describe('animals', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('fetchAnimals envia Bearer e X-Titan-Organization-Id sem filtros', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [], limit: 50, offset: 0, has_more: false }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const resultado = await fetchAnimals(options)

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/v1/livestock/animals',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer meu-token',
          'X-Titan-Organization-Id': 'org-1',
        }),
      }),
    )
    expect(resultado).toEqual({ items: [], limit: 50, offset: 0, has_more: false })
  })

  it('fetchAnimals monta a query string com identifier/limit/offset', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [], limit: 10, offset: 20, has_more: false }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchAnimals(options, { identifier: 'BR998', limit: 10, offset: 20 })

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/v1/livestock/animals?identifier=BR998&limit=10&offset=20',
      expect.anything(),
    )
  })

  it('fetchAnimal busca o detalhe pelo id', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ animal_id: 'a1', sex: 'FEMALE' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchAnimal(options, 'a1')

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/v1/livestock/animals/a1',
      expect.anything(),
    )
  })

  it('fetchProperty busca a propriedade pelo id', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ property_id: 'p1', name: 'Fazenda' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchProperty(options, 'p1')

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/v1/livestock/properties/p1',
      expect.anything(),
    )
  })

  it('fetchAnimalTimeline busca a timeline pelo id', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ animal_id: 'a1', known_until: null, entry_count: 0, entries: [] }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchAnimalTimeline(options, 'a1')

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/v1/livestock/animals/a1/timeline',
      expect.anything(),
    )
  })

  it('lança AnimalApiError com o reason_code do corpo em respostas de erro', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        json: async () => ({
          reason_code: 'PERMISSAO_AUSENTE',
          detail: 'A operação exige a permissão LIVESTOCK_ANIMAL.LER.',
        }),
      }),
    )

    await expect(fetchAnimals(options)).rejects.toMatchObject({
      status: 403,
      reasonCode: 'PERMISSAO_AUSENTE',
    })
    await expect(fetchAnimals(options)).rejects.toBeInstanceOf(AnimalApiError)
  })

  it('lança AnimalApiError com reasonCode nulo quando o corpo não é JSON', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => {
          throw new Error('não é JSON')
        },
      }),
    )

    await expect(fetchAnimal(options, 'a1')).rejects.toMatchObject({
      status: 500,
      reasonCode: null,
    })
  })
})
