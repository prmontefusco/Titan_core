import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { CommercialPassport } from './CommercialPassport'

const options = {
  baseUrl: 'http://127.0.0.1:8000',
  accessToken: 'meu-token',
  organizationId: 'org-producer',
}

function renderTela() {
  return render(<CommercialPassport {...options} />)
}

describe('CommercialPassport', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    cleanup()
  })

  it('consulta a rota release-gated com propriedade e temporalidade', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({
        reason_code: 'COMMERCIAL_PASSPORT_PIPELINE_NAO_HABILITADO',
        detail: 'pipeline interna desligada',
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    renderTela()

    fireEvent.change(screen.getByLabelText(/property id/i), {
      target: { value: '11111111-1111-1111-1111-111111111111' },
    })
    fireEvent.click(screen.getByRole('button', { name: /consultar passaporte/i }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    const [url, init] = fetchMock.mock.calls[0]

    expect(url).toContain(
      'http://127.0.0.1:8000/v1/livestock/properties/11111111-1111-1111-1111-111111111111/commercial-passport?',
    )
    expect(url).toContain('reference_time=')
    expect(url).toContain('knowledge_cutoff=')
    expect(init.headers.Authorization).toBe('Bearer meu-token')
    expect(init.headers['X-Titan-Organization-Id']).toBe('org-producer')
  })

  it('trata 503 como capacidade indisponível sem expor detalhe operacional bruto', async () => {
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

    renderTela()
    fireEvent.change(screen.getByLabelText(/property id/i), {
      target: { value: '11111111-1111-1111-1111-111111111111' },
    })
    fireEvent.click(screen.getByRole('button', { name: /consultar passaporte/i }))

    const alerta = await screen.findByRole('alert')
    expect(alerta).toHaveTextContent(/não está habilitado/i)
    expect(alerta).not.toHaveTextContent(/pipeline interna desligada/i)
  })

  it('renderiza projection real separando readiness de propriedade e população', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          property_id: 'p1',
          reference_time: '2026-09-11T00:00:00Z',
          knowledge_cutoff: '2026-09-11T00:00:00Z',
          evaluated_at: '2026-09-11T00:00:00Z',
          result_boundary: 'MARKET_ELIGIBILITY_ASSESSMENT_NOT_EXPORT_AUTHORIZATION',
          opportunities: [
            {
              opportunity: {
                code: 'synthetic-eu',
                kind: 'MARKET',
                name: 'European Union',
                purpose: 'export-eu',
                policy_id: 'policy-1',
                policy_version: 1,
              },
              property_readiness: {
                interpretation: 'PARTIALLY_READY',
                breakdown: {
                  satisfied: 18,
                  missing: 2,
                  unknown: 1,
                  failed: 0,
                  not_applicable: 1,
                  blocked: 0,
                  applicable_count: 21,
                  total_count: 22,
                  derived_ratio: { satisfied: 18, applicable: 21 },
                },
                requirements: [
                  {
                    requirement_code: 'environmental-evidence',
                    label: 'Environmental evidence',
                    dimension: 'PROPERTY_READINESS',
                    status: 'MISSING',
                    reason: 'Required evidence has not been supplied.',
                    reason_codes: ['MISSING_EVIDENCE'],
                    limitations: [],
                  },
                ],
              },
              population_eligibility: {
                subject_type: 'animal',
                counts_by_status: {
                  READY: 742,
                  INDETERMINATE: 103,
                  NOT_READY: 377,
                },
                total_count: 1222,
                source_report_reference: 'market-readiness:synthetic-eu',
                limitations: [],
              },
              limitations: [],
            },
          ],
          limitations: [],
        }),
      }),
    )

    renderTela()
    fireEvent.change(screen.getByLabelText(/property id/i), {
      target: { value: '11111111-1111-1111-1111-111111111111' },
    })
    fireEvent.click(screen.getByRole('button', { name: /consultar passaporte/i }))

    expect(await screen.findByText(/oportunidades comerciais/i)).toBeInTheDocument()
    expect(screen.getByText('European Union')).toBeInTheDocument()
    expect(screen.getByText('PARTIALLY_READY')).toBeInTheDocument()
    expect(screen.getByText('Environmental evidence: MISSING')).toBeInTheDocument()
    expect(screen.getByText('READY: 742')).toBeInTheDocument()
    expect(screen.getByText('INDETERMINATE: 103')).toBeInTheDocument()
  })
})
