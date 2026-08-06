import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  DecisionReviewApiError,
  fetchDossier,
  fetchProposal,
  submitReview,
} from './decisionReview'

const options = {
  baseUrl: 'http://127.0.0.1:8000',
  accessToken: 'meu-token',
  organizationId: 'org-1',
}

describe('decisionReview', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('fetchProposal faz GET no endpoint da proposta', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ proposal_id: 'p1', purpose: 'eligibility', current_proposal: true }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchProposal(options, 'p1')

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/v1/livestock/decision-proposals/p1',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer meu-token',
          'X-Titan-Organization-Id': 'org-1',
        }),
      }),
    )
  })

  it('submitReview envia conclusion e reasoning', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({
        proposal_id: 'p1',
        review_id: 'r1',
        workflow_status: 'DECISION_EMITTED',
        decision_id: 'd1',
        dossier_id: 'ds1',
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await submitReview(options, 'p1', { conclusion: 'APROVA', reasoning: 'Motivo aceito.' })

    const chamada = fetchMock.mock.calls[0]
    expect(chamada[0]).toBe('http://127.0.0.1:8000/v1/livestock/decision-proposals/p1/reviews')
    expect(chamada[1].method).toBe('POST')
    expect(JSON.parse(chamada[1].body)).toEqual({
      conclusion: 'APROVA',
      reasoning: 'Motivo aceito.',
    })
  })

  it('fetchDossier faz GET no endpoint do dossiê', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ dossier_id: 'ds1', document: {} }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchDossier(options, 'ds1')

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/v1/livestock/dossiers/ds1',
      expect.anything(),
    )
  })

  it('mapeia erro 404 para DecisionReviewApiError com reason_code', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ reason_code: 'RECURSO_NAO_ENCONTRADO', detail: 'não encontrada' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(fetchProposal(options, 'inexistente')).rejects.toMatchObject({
      status: 404,
      reasonCode: 'RECURSO_NAO_ENCONTRADO',
    })
    await expect(fetchProposal(options, 'inexistente')).rejects.toBeInstanceOf(
      DecisionReviewApiError,
    )
  })
})
