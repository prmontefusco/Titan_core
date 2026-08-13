import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  PolicyGovernanceApiError,
  createPolicy,
  executeGovernanceFlow,
  fetchMarketRuleCatalog,
  listPolicies,
  publishPolicy,
  suggestGovernanceFlow,
} from './policyGovernance'

const options = {
  baseUrl: 'http://127.0.0.1:8000',
  accessToken: 'meu-token',
  organizationId: 'org-1',
}

describe('policyGovernance', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('listPolicies faz GET na lista de policies', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [], limit: 200, offset: 0, has_more: false }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await listPolicies(options)

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/v1/rule-governance/policies?limit=200',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer meu-token',
          'X-Titan-Organization-Id': 'org-1',
        }),
      }),
    )
  })

  it('createPolicy envia code, name e description', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({ policy_id: 'pol-1', status: 'draft' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await createPolicy(options, { code: 'politica-china', name: 'China' })

    const chamada = fetchMock.mock.calls[0]
    expect(chamada[0]).toBe('http://127.0.0.1:8000/v1/rule-governance/policies')
    expect(chamada[1].method).toBe('POST')
    expect(JSON.parse(chamada[1].body)).toEqual({
      code: 'politica-china',
      name: 'China',
      description: '',
    })
  })

  it('publishPolicy faz POST no endpoint de publicação', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ policy_id: 'pol-1', status: 'published' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await publishPolicy(options, 'pol-1')

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/v1/rule-governance/policies/pol-1/publish',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('fetchMarketRuleCatalog faz GET no catálogo', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ catalog_version: 1, vertical: 'livestock', fact_types: [], templates: [] }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchMarketRuleCatalog(options)

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/v1/rule-governance/catalogs/livestock-market-rules',
      expect.anything(),
    )
  })

  it('suggestGovernanceFlow envia os parametros do template', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        template_code: 'sanitary-requirement-campaign-v1',
        identity: {},
        version: {},
        adoption: {},
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await suggestGovernanceFlow(options, 'sanitary-requirement-campaign-v1', {
      marketPurpose: 'exportacao-china',
      adoptionScope: 'livestock.animal',
      name: 'Brucelose China',
      parameters: { campaign_code: 'brucelose' },
    })

    const chamada = fetchMock.mock.calls[0]
    expect(chamada[0]).toBe(
      'http://127.0.0.1:8000/v1/rule-governance/catalogs/livestock-market-rules/templates/sanitary-requirement-campaign-v1/governance-flow',
    )
    expect(JSON.parse(chamada[1].body)).toMatchObject({
      market_purpose: 'exportacao-china',
      adoption_scope: 'livestock.animal',
      name: 'Brucelose China',
      parameters: { campaign_code: 'brucelose' },
    })
  })

  it('executeGovernanceFlow envia policy_id e create_adoption', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({
        template_code: 'sanitary-requirement-campaign-v1',
        identity: {},
        version: {},
        adoption: null,
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await executeGovernanceFlow(options, 'sanitary-requirement-campaign-v1', {
      marketPurpose: 'exportacao-china',
      adoptionScope: 'livestock.animal',
      name: 'Brucelose China',
      parameters: { campaign_code: 'brucelose' },
      policyId: 'pol-1',
      createAdoption: true,
    })

    const chamada = fetchMock.mock.calls[0]
    expect(JSON.parse(chamada[1].body)).toMatchObject({
      policy_id: 'pol-1',
      create_adoption: true,
    })
  })

  it('mapeia erro 403 para PolicyGovernanceApiError com reason_code', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ reason_code: 'PERMISSAO_AUSENTE', detail: 'sem permissão' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(fetchMarketRuleCatalog(options)).rejects.toMatchObject({
      status: 403,
      reasonCode: 'PERMISSAO_AUSENTE',
    })
    await expect(fetchMarketRuleCatalog(options)).rejects.toBeInstanceOf(PolicyGovernanceApiError)
  })
})
