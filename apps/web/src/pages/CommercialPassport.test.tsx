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
                population_snapshot_digest: 'population:sha256:abc',
                selection_criteria_digest: 'criteria:sha256:def',
                commercial_window: {
                  start: '2026-09-12T00:00:00+00:00',
                  end: '2026-10-11T00:00:00+00:00',
                },
                limitations: [],
              },
              limitations: [],
            },
          ],
          gap_analysis: {
            gap_count: 2,
            category_counts: {
              MISSING: 1,
              UNKNOWN: 0,
              EXPIRED: 0,
              INSUFFICIENT: 1,
              BLOCKING: 0,
            },
            gaps: [
              {
                opportunity_code: 'synthetic-eu',
                opportunity_name: 'European Union',
                dimension: 'PROPERTY_READINESS',
                subject_scope: 'property',
                gap_code: 'environmental-evidence',
                label: 'Environmental evidence',
                category: 'MISSING',
                reason: 'Required evidence has not been supplied.',
                reason_codes: ['MISSING_EVIDENCE'],
                recommended_action: {
                  action_code: 'PROVIDE_EVIDENCE',
                  description: 'Attach or register the missing evidence before reassessment.',
                },
                affected_count: null,
                limitations: [],
              },
              {
                opportunity_code: 'synthetic-eu',
                opportunity_name: 'European Union',
                dimension: 'POPULATION_ELIGIBILITY',
                subject_scope: 'animal',
                gap_code: 'synthetic-eu:population:NOT_READY',
                label: 'animal population not_ready',
                category: 'INSUFFICIENT',
                reason: '377 animal(s) are NOT_READY for this opportunity.',
                reason_codes: ['NOT_READY'],
                recommended_action: {
                  action_code: 'REVIEW_FAILED_REQUIREMENTS',
                  description: 'Review failed requirements and correct the operational condition.',
                },
                affected_count: 377,
                limitations: [],
              },
            ],
            limitations: [
              'COMMERCIAL_GAP_ANALYSIS_IS_OPERATIONAL_GUIDANCE',
              'COMMERCIAL_GAP_ANALYSIS_IS_NOT_REGULATORY_DECISION',
            ],
          },
          evidence_vault: {
            need_count: 2,
            missing_count: 2,
            status_counts: {
              SATISFIED: 0,
              MISSING: 1,
              UNKNOWN: 0,
              EXPIRED: 0,
              INSUFFICIENT: 1,
              BLOCKING: 0,
            },
            needs: [
              {
                need_code: 'synthetic-eu:environmental-evidence',
                opportunity_code: 'synthetic-eu',
                opportunity_name: 'European Union',
                evidence_type: 'livestock.property_environmental_evidence',
                purpose: 'export-eu',
                subject_scope: 'property',
                status: 'MISSING',
                source_gap_code: 'environmental-evidence',
                expected_coverage: 'property at Commercial Passport reference_time',
                recommended_action: 'Attach or register the missing evidence before reassessment.',
                referenced_evidence_ids: [],
                limitations: [],
              },
              {
                need_code: 'synthetic-eu:population:NOT_READY',
                opportunity_code: 'synthetic-eu',
                opportunity_name: 'European Union',
                evidence_type: 'livestock.corrective_evidence',
                purpose: 'export-eu',
                subject_scope: 'animal',
                status: 'INSUFFICIENT',
                source_gap_code: 'synthetic-eu:population:NOT_READY',
                expected_coverage: '377 animal(s) in population eligibility',
                recommended_action: 'Review failed requirements and correct the operational condition.',
                referenced_evidence_ids: ['evidence-1'],
                limitations: [],
              },
            ],
            limitations: [
              'PRODUCER_EVIDENCE_VAULT_IS_OPERATIONAL_INDEX',
              'PRODUCER_EVIDENCE_VAULT_DOES_NOT_REPLACE_CORE_EVIDENCE',
            ],
          },
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
    expect(screen.getByText(/rastreio da população/i)).toBeInTheDocument()
    expect(screen.getByText(/não expõe IDs individuais de animais/i)).toBeInTheDocument()
    expect(screen.getByText('population:sha256:abc')).toBeInTheDocument()
    expect(screen.getByText('criteria:sha256:def')).toBeInTheDocument()
    expect(screen.getByText('market-readiness:synthetic-eu')).toBeInTheDocument()
    expect(screen.getByText(/lacunas e próximas ações/i)).toBeInTheDocument()
    expect(screen.getByText('Lacunas acionáveis')).toBeInTheDocument()
    expect(screen.getAllByText('MISSING').length).toBeGreaterThan(0)
    expect(screen.getAllByText('INSUFFICIENT').length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Attach or register the missing evidence/i).length).toBeGreaterThan(
      0,
    )
    expect(screen.getByText(/Afeta 377 item/i)).toBeInTheDocument()
    expect(screen.getByText(/não são decisão regulatória/i)).toBeInTheDocument()
    expect(screen.getByText(/cofre de evidências/i)).toBeInTheDocument()
    expect(screen.getByText('Necessidades de evidência')).toBeInTheDocument()
    expect(screen.getByText('livestock.property_environmental_evidence')).toBeInTheDocument()
    expect(screen.getByText('livestock.corrective_evidence')).toBeInTheDocument()
    expect(screen.getByText(/property at Commercial Passport reference_time/i)).toBeInTheDocument()
    expect(screen.getByText(/Evidências referenciadas: evidence-1/i)).toBeInTheDocument()
    expect(screen.getByText(/não substitui Evidence do Core/i)).toBeInTheDocument()
  })
})
