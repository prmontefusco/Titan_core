import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  TreatmentApiError,
  fetchMedicationBatches,
  fetchMedications,
  registerTreatment,
} from './treatments'

const options = {
  baseUrl: 'http://127.0.0.1:8000',
  accessToken: 'meu-token',
  organizationId: 'org-1',
}

describe('treatments', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('fetchMedications envia Bearer e X-Titan-Organization-Id', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [], limit: 50, offset: 0, has_more: false }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchMedications(options)

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/v1/livestock/medications',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer meu-token',
          'X-Titan-Organization-Id': 'org-1',
        }),
      }),
    )
  })

  it('fetchMedicationBatches filtra por medicationId quando informado', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [], limit: 50, offset: 0, has_more: false }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchMedicationBatches(options, { medicationId: 'm1' })

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/v1/livestock/medication-batches?medication_id=m1',
      expect.anything(),
    )
  })

  it('fetchMedicationBatches sem medicationId não acrescenta query string', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [], limit: 50, offset: 0, has_more: false }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchMedicationBatches(options)

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/v1/livestock/medication-batches',
      expect.anything(),
    )
  })

  it('registerTreatment envia o corpo esperado pelo backend', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({
        application_id: 'app-1',
        animal_id: 'a1',
        medication_batch_id: 'b1',
        applied_at: '2026-08-01T12:00:00Z',
        dose: '10ml',
        prescription_id: null,
        sanitary_campaign_id: null,
        corrects_application_id: null,
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await registerTreatment(options, {
      animalId: 'a1',
      medicationBatchId: 'b1',
      appliedAt: '2026-08-01T12:00:00Z',
      dose: '10ml',
      evidenceNotes: ['nota'],
    })

    const chamada = fetchMock.mock.calls[0]
    expect(chamada[0]).toBe('http://127.0.0.1:8000/v1/livestock/treatments')
    expect(chamada[1].method).toBe('POST')
    expect(JSON.parse(chamada[1].body)).toEqual({
      animal_id: 'a1',
      medication_batch_id: 'b1',
      applied_at: '2026-08-01T12:00:00Z',
      dose: '10ml',
      evidence_notes: ['nota'],
    })
  })

  it('registerTreatment envia dose null e evidence_notes vazio quando omitidos', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({
        application_id: 'app-1',
        animal_id: 'a1',
        medication_batch_id: 'b1',
        applied_at: '2026-08-01T12:00:00Z',
        dose: null,
        prescription_id: null,
        sanitary_campaign_id: null,
        corrects_application_id: null,
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await registerTreatment(options, {
      animalId: 'a1',
      medicationBatchId: 'b1',
      appliedAt: '2026-08-01T12:00:00Z',
    })

    const chamada = fetchMock.mock.calls[0]
    expect(JSON.parse(chamada[1].body)).toEqual({
      animal_id: 'a1',
      medication_batch_id: 'b1',
      applied_at: '2026-08-01T12:00:00Z',
      dose: null,
      evidence_notes: [],
    })
  })

  it('lança TreatmentApiError com o reason_code do corpo em respostas de erro', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 409,
        json: async () => ({
          reason_code: 'CONFLITO_DE_DOMINIO',
          detail: 'applied_at não pode estar no futuro.',
        }),
      }),
    )

    await expect(
      registerTreatment(options, {
        animalId: 'a1',
        medicationBatchId: 'b1',
        appliedAt: '2099-01-01T00:00:00Z',
      }),
    ).rejects.toMatchObject({
      status: 409,
      reasonCode: 'CONFLITO_DE_DOMINIO',
    })
    await expect(
      registerTreatment(options, {
        animalId: 'a1',
        medicationBatchId: 'b1',
        appliedAt: '2099-01-01T00:00:00Z',
      }),
    ).rejects.toBeInstanceOf(TreatmentApiError)
  })
})
