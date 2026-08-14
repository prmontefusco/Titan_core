import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { TerritorialCaptureQa } from './TerritorialCaptureQa'

const options = {
  baseUrl: 'http://127.0.0.1:8000',
  accessToken: 'meu-token',
  organizationId: 'org-1',
}

function resposta(corpo: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => corpo,
  }
}

describe('TerritorialCaptureQa', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.unstubAllEnvs()
    cleanup()
  })

  it('não chama API antes do clique', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    render(<TerritorialCaptureQa {...options} />)

    expect(fetchMock).not.toHaveBeenCalled()
    expect(screen.getByText(/não emite Policy, Evaluation, Decision ou Dossier/i)).toBeInTheDocument()
  })

  it('executa o cenário sintético e exibe as capturas sem alegar conformidade', async () => {
    vi.stubGlobal('crypto', { randomUUID: () => '12345678-0000-4000-8000-000000000000' })
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        resposta({ property_id: 'p1', code: 'TERR-QA-12345678', name: 'Fazenda QA' }, 201),
      )
      .mockResolvedValueOnce(
        resposta(
          {
            geometry_id: 'g1',
            property_id: 'p1',
            source: 'DECLARADA',
            layer: 'AREA_IMOVEL',
            srid: 4326,
            source_digest: 'geo-digest',
            external_reference: null,
            version: 1,
            captured_at: null,
            imported_at: '2026-08-14T00:00:00Z',
          },
          201,
        ),
      )
      .mockResolvedValueOnce(resposta({ capture_id: 'c-overlap', response_digest: 'd1' }, 201))
      .mockResolvedValueOnce(resposta({ capture_id: 'c-timeline', response_digest: 'd2' }, 201))
      .mockResolvedValueOnce(
        resposta({
          items: [
            {
              capture_id: 'c-overlap',
              property_id: 'p1',
              geometry_id: 'g1',
              geometry_version: 1,
              source_profile_code: 'TERRITORIAL_TEST_SOURCE',
              source_environment: 'SYNTHETIC',
              source_layer: 'TERRITORIAL_TEST_OVERLAP',
              operation: 'OVERLAP',
              request_scope_digest: 'rs1',
              response_schema: 'livestock.territorial.synthetic_capture_response',
              response_schema_version: 1,
              canonicalization_version: 'TERRITORIAL_RESPONSE_SUMMARY_CANONICAL_JSON_V1',
              response_digest: 'digest-overlap',
              response_summary: { profile: 'FUNAI_LIKE_OVERLAP', operation: 'OVERLAP' },
              source_version_ids: ['FUNAI_TEST_2026_V1'],
              source_valid_from: null,
              source_valid_to: null,
              captured_at: '2026-03-01T00:00:00Z',
              known_at: '2026-03-02T00:00:00Z',
              recorded_at: '2026-08-14T00:00:00Z',
              limitations: ['NO_EXTERNAL_RECOGNITION_ASSERTED'],
            },
            {
              capture_id: 'c-timeline',
              property_id: 'p1',
              geometry_id: 'g1',
              geometry_version: 1,
              source_profile_code: 'TERRITORIAL_TEST_SOURCE',
              source_environment: 'SYNTHETIC',
              source_layer: 'TERRITORIAL_TEST_TIMELINE',
              operation: 'TIMELINE',
              request_scope_digest: 'rs2',
              response_schema: 'livestock.territorial.synthetic_capture_response',
              response_schema_version: 1,
              canonicalization_version: 'TERRITORIAL_RESPONSE_SUMMARY_CANONICAL_JSON_V1',
              response_digest: 'digest-timeline',
              response_summary: { profile: 'PRODES_LIKE_TIMELINE', operation: 'TIMELINE' },
              source_version_ids: ['PRODES_TEST_2024_V1'],
              source_valid_from: '2024-01-01T00:00:00Z',
              source_valid_to: '2025-01-01T00:00:00Z',
              captured_at: '2026-03-01T00:00:00Z',
              known_at: '2026-03-02T00:00:00Z',
              recorded_at: '2026-08-14T00:00:00Z',
              limitations: ['SYNTHETIC_SOURCE_ONLY'],
            },
          ],
          limit: 50,
          offset: 0,
          has_more: false,
        }),
      )
    vi.stubGlobal('fetch', fetchMock)

    render(<TerritorialCaptureQa {...options} />)
    fireEvent.click(screen.getByRole('button', { name: /criar cenário sintético/i }))

    expect(await screen.findByText(/Capturas sintéticas preservadas: 2/i)).toBeInTheDocument()
    expect(screen.getByText(/FUNAI_LIKE_OVERLAP \/ OVERLAP/i)).toBeInTheDocument()
    expect(screen.getByText(/PRODES_LIKE_TIMELINE \/ TIMELINE/i)).toBeInTheDocument()
    expect(screen.getByRole('note')).toHaveTextContent(/não é conformidade/i)
    expect(fetchMock).toHaveBeenCalledTimes(5)
  })

  it('mostra erro de API com reason_code', async () => {
    vi.stubGlobal('crypto', { randomUUID: () => '12345678-0000-4000-8000-000000000000' })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        resposta(
          {
            reason_code: 'PERMISSAO_AUSENTE',
            detail: 'A operação exige permissão.',
          },
          403,
        ),
      ),
    )

    render(<TerritorialCaptureQa {...options} />)
    fireEvent.click(screen.getByRole('button', { name: /criar cenário sintético/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/PERMISSAO_AUSENTE/)
  })
})
