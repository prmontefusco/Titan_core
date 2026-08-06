import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  EligibilityApiError,
  fetchExternalCounterparties,
  runAnimalEligibility,
  runCommercialExplanation,
  runMarketEvaluation,
} from './eligibility'

const options = {
  baseUrl: 'http://127.0.0.1:8000',
  accessToken: 'meu-token',
  organizationId: 'org-1',
}

describe('eligibility', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('runAnimalEligibility faz POST no endpoint do animal', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({ animal_id: 'a1', result: 'APROVADA', outcome: 'ELEGIVEL' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await runAnimalEligibility(options, 'a1')

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/v1/livestock/animals/a1/eligibility',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          Authorization: 'Bearer meu-token',
          'X-Titan-Organization-Id': 'org-1',
        }),
      }),
    )
  })

  it('runMarketEvaluation envia animal_id e slaughterhouse_counterparty_id', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({ animal_id: 'a1', markets: [] }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await runMarketEvaluation(options, { animalId: 'a1', slaughterhouseCounterpartyId: 'c1' })

    const chamada = fetchMock.mock.calls[0]
    expect(chamada[0]).toBe('http://127.0.0.1:8000/v1/livestock/market-eligibility/evaluations')
    expect(JSON.parse(chamada[1].body)).toEqual({
      animal_id: 'a1',
      slaughterhouse_counterparty_id: 'c1',
    })
  })

  it('runMarketEvaluation envia slaughterhouse_counterparty_id nulo quando omitido', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({ animal_id: 'a1', markets: [] }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await runMarketEvaluation(options, { animalId: 'a1' })

    const chamada = fetchMock.mock.calls[0]
    expect(JSON.parse(chamada[1].body)).toEqual({
      animal_id: 'a1',
      slaughterhouse_counterparty_id: null,
    })
  })

  it('runCommercialExplanation faz POST no endpoint de explicação comercial', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({ subject_id: 'a1', markets: [] }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await runCommercialExplanation(options, { animalId: 'a1' })

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/v1/livestock/market-eligibility/commercial-explanations',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('fetchExternalCounterparties busca a lista de contrapartes', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [], limit: 50, offset: 0, has_more: false }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchExternalCounterparties(options)

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/v1/livestock/external-counterparties',
      expect.anything(),
    )
  })

  it('lança EligibilityApiError com o corpo inteiro em respostas de erro genéricas', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({ reason_code: 'RECURSO_NAO_ENCONTRADO', detail: 'não encontrado' }),
      }),
    )

    await expect(runAnimalEligibility(options, 'a1')).rejects.toMatchObject({
      status: 404,
      reasonCode: 'RECURSO_NAO_ENCONTRADO',
    })
    await expect(runAnimalEligibility(options, 'a1')).rejects.toBeInstanceOf(EligibilityApiError)
  })

  it('detecta revisão humana necessária e expõe proposal_id', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 409,
        json: async () => ({
          reason_code: 'REVISAO_HUMANA_NECESSARIA',
          detail: 'A emissão automática foi recusada.',
          proposal_id: 'p1',
          evaluation_outcome: 'REVISAO_HUMANA_NECESSARIA',
          knowledge_limitations: [],
        }),
      }),
    )

    try {
      await runAnimalEligibility(options, 'a1')
      throw new Error('deveria ter lançado EligibilityApiError')
    } catch (erro) {
      expect(erro).toBeInstanceOf(EligibilityApiError)
      const apiError = erro as EligibilityApiError
      expect(apiError.requiresHumanReview).toBe(true)
      expect(apiError.proposalId).toBe('p1')
    }
  })

  it('requiresHumanReview é falso para outros 409', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 409,
        json: async () => ({ reason_code: 'CONFLITO_DE_DOMINIO', detail: 'conflito' }),
      }),
    )

    try {
      await runAnimalEligibility(options, 'a1')
      throw new Error('deveria ter lançado EligibilityApiError')
    } catch (erro) {
      const apiError = erro as EligibilityApiError
      expect(apiError.requiresHumanReview).toBe(false)
      expect(apiError.proposalId).toBeNull()
    }
  })
})
