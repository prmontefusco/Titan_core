import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MarketRuleGovernance } from './MarketRuleGovernance'

const options = {
  baseUrl: 'http://127.0.0.1:8000',
  accessToken: 'meu-token',
  organizationId: 'org-1',
}

function respostaCatalogo() {
  return {
    catalog_version: 1,
    vertical: 'livestock',
    fact_types: [],
    templates: [
      {
        template_code: 'sanitary-requirement-campaign-v1',
        rule_code: 'rule-exigibilidade-sanitaria',
        name: 'Campanha sanitaria obrigatoria',
        purpose_hint: 'Usar quando o mercado exige uma campanha ou vacina especifica.',
        scope_hint: 'livestock.animal',
        normative_source_hint: '',
        required_evidence_types: [],
        conditions: [
          {
            fact_type: 'livestock.sanitary_requirement.{{campaign_code}}',
            payload_key: 'status',
            operator: 'equals',
            expected_value: 'SATISFEITO',
            description: 'A campanha sanitaria exigida precisa estar satisfeita.',
          },
        ],
        justification_hint: '',
        corrective_action_hint: '',
        parameters: [
          {
            name: 'campaign_code',
            description: 'Codigo canonico da campanha sanitaria exigida',
            example: 'brucelose',
          },
        ],
      },
    ],
  }
}

function respostaPolicies(items: unknown[] = []) {
  return { items, limit: 200, offset: 0, has_more: false }
}

function fetchMockPadrao(handlers: Record<string, () => unknown>) {
  return vi.fn((url: string, init?: RequestInit) => {
    void init
    for (const [trecho, resposta] of Object.entries(handlers)) {
      if (url.includes(trecho)) {
        return Promise.resolve({ ok: true, status: 200, json: async () => resposta() })
      }
    }
    throw new Error(`URL não mapeada no mock: ${url}`)
  })
}

describe('MarketRuleGovernance', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    cleanup()
  })

  it('carrega o catálogo e lista os modelos disponíveis', async () => {
    vi.stubGlobal(
      'fetch',
      fetchMockPadrao({
        'catalogs/livestock-market-rules': respostaCatalogo,
        '/policies': () => respostaPolicies(),
      }),
    )

    render(<MarketRuleGovernance {...options} />)

    expect(
      await screen.findByRole('option', { name: 'Campanha sanitaria obrigatoria' }),
    ).toBeInTheDocument()
  })

  it('mostra mensagem de permissão ausente quando o catálogo responde 403', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        json: async () => ({ reason_code: 'PERMISSAO_AUSENTE' }),
      }),
    )

    render(<MarketRuleGovernance {...options} />)

    expect(await screen.findByText(/não tem permissão/i)).toBeInTheDocument()
  })

  it('pré-visualiza e depois confirma o fluxo completo', async () => {
    const fetchMock = vi.fn((url: string, init?: RequestInit) => {
      const metodo = init?.method ?? 'GET'
      if (url.includes('catalogs/livestock-market-rules') && metodo === 'GET') {
        return Promise.resolve({ ok: true, status: 200, json: async () => respostaCatalogo() })
      }
      if (url.endsWith('/v1/rule-governance/policies?limit=200')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () =>
            respostaPolicies([
              {
                policy_id: 'pol-1',
                organization_id: 'org-1',
                code: 'politica-china',
                name: 'China',
                description: '',
                version: 1,
                status: 'published',
                valid_from: null,
                valid_to: null,
                created_at: '2026-08-01T00:00:00Z',
                published_at: '2026-08-01T00:00:00Z',
              },
            ]),
        })
      }
      if (url.endsWith('/governance-flow')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            template_code: 'sanitary-requirement-campaign-v1',
            identity: {
              code: 'rule-exigibilidade-sanitaria',
              purpose: 'Aplicar regra',
              scope: 'livestock.animal',
              source_type: 'politica_interna',
              vertical: 'livestock',
              description: '',
            },
            version: {
              template_code: 'sanitary-requirement-campaign-v1',
              rule_code: 'rule-exigibilidade-sanitaria',
              name: 'Brucelose China',
              description: '',
              severity: 'blocking',
              normative_source: '',
              required_evidence_types: [],
              conditions: [
                {
                  fact_type: 'livestock.sanitary_requirement.brucelose',
                  payload_key: 'status',
                  operator: 'equals',
                  expected_value: 'SATISFEITO',
                  description: 'A campanha sanitaria exigida precisa estar satisfeita.',
                },
              ],
              justification: '',
              corrective_action: '',
            },
            adoption: { purpose: 'exportacao-china', scope: 'livestock.animal', reason: '' },
          }),
        })
      }
      if (url.endsWith('/execute')) {
        return Promise.resolve({
          ok: true,
          status: 201,
          json: async () => ({
            template_code: 'sanitary-requirement-campaign-v1',
            identity: {
              rule_identity_id: 'ri-1',
              organization_id: 'org-1',
              code: 'rule-exigibilidade-sanitaria',
              purpose: '',
              scope: '',
              source_type: 'politica_interna',
              vertical: 'livestock',
              description: '',
              created_at: '2026-08-13T00:00:00Z',
            },
            version: {
              rule_id: 'rule-1',
              policy_id: 'pol-1',
              organization_id: 'org-1',
              code: 'rule-exigibilidade-sanitaria',
              version: 1,
              name: 'Brucelose China',
              description: '',
              severity: 'blocking',
              normative_source: '',
              required_evidence_types: [],
              conditions: [],
              justification: '',
              corrective_action: '',
              valid_from: null,
              valid_to: null,
              created_at: '2026-08-13T00:00:00Z',
            },
            adoption: {
              adoption_id: 'ad-1',
              organization_id: 'org-1',
              rule_identity_id: 'ri-1',
              rule_version_id: 'rule-1',
              purpose: 'exportacao-china',
              scope: 'livestock.animal',
              adopted_at: '2026-08-13T00:00:00Z',
              reason: '',
              status: 'active',
            },
          }),
        })
      }
      throw new Error(`URL não mapeada no mock: ${url} (${metodo})`)
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<MarketRuleGovernance {...options} />)

    fireEvent.change(await screen.findByLabelText('Modelo'), {
      target: { value: 'sanitary-requirement-campaign-v1' },
    })
    fireEvent.change(await screen.findByLabelText(/campanha sanitaria exigida/i), {
      target: { value: 'brucelose' },
    })
    fireEvent.change(screen.getByLabelText(/mercado \(purpose\)/i), {
      target: { value: 'exportacao-china' },
    })
    fireEvent.change(screen.getByLabelText(/nome da regra/i), {
      target: { value: 'Brucelose China' },
    })

    fireEvent.click(screen.getByRole('button', { name: /pré-visualizar/i }))

    expect(await screen.findByText(/pré-visualização/i)).toBeInTheDocument()
    expect(screen.getByText(/brucelose china/i)).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText(/usar política existente/i), {
      target: { value: 'pol-1' },
    })
    fireEvent.click(screen.getByRole('button', { name: /confirmar e publicar/i }))

    expect(await screen.findByText(/regra publicada/i)).toBeInTheDocument()
    expect(screen.getByText('ri-1')).toBeInTheDocument()
  })
})
