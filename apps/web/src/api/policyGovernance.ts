// Mesmo padrão de api/decisionReview.ts: reason_code/detail bastam para o que
// esta tela precisa decidir (403 sem permissão, 409 código repetido ou já
// publicada, 404 inexistente).

interface RequestOptions {
  baseUrl: string
  accessToken: string
  organizationId: string
}

export class PolicyGovernanceApiError extends Error {
  readonly status: number
  readonly reasonCode: string | null

  constructor(status: number, reasonCode: string | null, detail?: string) {
    super(detail ?? `Requisição recusada (${status}).`)
    this.status = status
    this.reasonCode = reasonCode
  }
}

async function chamar<T>(
  path: string,
  { baseUrl, accessToken, organizationId }: RequestOptions,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'X-Titan-Organization-Id': organizationId,
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...init.headers,
    },
  })

  if (!response.ok) {
    const corpo = await response.json().catch(() => null)
    throw new PolicyGovernanceApiError(response.status, corpo?.reason_code ?? null, corpo?.detail)
  }

  return (await response.json()) as T
}

export interface PolicyResponse {
  policy_id: string
  organization_id: string
  code: string
  name: string
  description: string
  version: number
  status: 'draft' | 'published' | 'superseded' | 'revoked'
  valid_from: string | null
  valid_to: string | null
  created_at: string
  published_at: string | null
}

export function listPolicies(options: RequestOptions): Promise<{ items: PolicyResponse[] }> {
  return chamar<{ items: PolicyResponse[] }>('/v1/rule-governance/policies?limit=200', options)
}

export function createPolicy(
  options: RequestOptions,
  params: { code: string; name: string; description?: string },
): Promise<PolicyResponse> {
  return chamar<PolicyResponse>('/v1/rule-governance/policies', options, {
    method: 'POST',
    body: JSON.stringify({
      code: params.code,
      name: params.name,
      description: params.description ?? '',
    }),
  })
}

export function publishPolicy(options: RequestOptions, policyId: string): Promise<PolicyResponse> {
  return chamar<PolicyResponse>(`/v1/rule-governance/policies/${policyId}/publish`, options, {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

export interface RuleFactTypeCatalog {
  fact_type: string
  description: string
  payload_keys: string[]
  parameterized: boolean
  example_fact_type: string | null
}

export interface RuleTemplateCondition {
  fact_type: string
  payload_key: string
  operator: string
  expected_value: unknown
  description: string
}

export interface RuleTemplateParameter {
  name: string
  description: string
  example: string
}

export interface RuleTemplateCatalog {
  template_code: string
  rule_code: string
  name: string
  purpose_hint: string
  scope_hint: string
  normative_source_hint: string
  required_evidence_types: string[]
  conditions: RuleTemplateCondition[]
  justification_hint: string
  corrective_action_hint: string
  parameters: RuleTemplateParameter[]
}

export interface LivestockMarketRuleCatalog {
  catalog_version: number
  vertical: string
  fact_types: RuleFactTypeCatalog[]
  templates: RuleTemplateCatalog[]
}

export function fetchMarketRuleCatalog(options: RequestOptions): Promise<LivestockMarketRuleCatalog> {
  return chamar<LivestockMarketRuleCatalog>(
    '/v1/rule-governance/catalogs/livestock-market-rules',
    options,
  )
}

export interface GovernanceFlowParams {
  marketPurpose: string
  adoptionScope: string
  name: string
  normativeSource?: string
  versionDescription?: string
  adoptionReason?: string
  parameters: Record<string, string>
}

export interface MaterializedRuleDraft {
  template_code: string
  rule_code: string
  name: string
  description: string
  severity: string
  normative_source: string
  required_evidence_types: string[]
  conditions: RuleTemplateCondition[]
  justification: string
  corrective_action: string
}

export interface SuggestedGovernanceFlow {
  template_code: string
  identity: {
    code: string
    purpose: string
    scope: string
    source_type: string
    vertical: string
    description: string
  }
  version: MaterializedRuleDraft
  adoption: { purpose: string; scope: string; reason: string }
}

export function suggestGovernanceFlow(
  options: RequestOptions,
  templateCode: string,
  params: GovernanceFlowParams,
): Promise<SuggestedGovernanceFlow> {
  return chamar<SuggestedGovernanceFlow>(
    `/v1/rule-governance/catalogs/livestock-market-rules/templates/${templateCode}/governance-flow`,
    options,
    {
      method: 'POST',
      body: JSON.stringify({
        market_purpose: params.marketPurpose,
        adoption_scope: params.adoptionScope,
        name: params.name,
        normative_source: params.normativeSource ?? '',
        version_description: params.versionDescription ?? '',
        adoption_reason: params.adoptionReason ?? '',
        parameters: params.parameters,
      }),
    },
  )
}

export interface RuleIdentity {
  rule_identity_id: string
  organization_id: string
  code: string
  purpose: string
  scope: string
  source_type: string
  vertical: string | null
  description: string
  created_at: string
}

export interface RuleVersion {
  rule_id: string
  policy_id: string
  organization_id: string
  code: string
  version: number
  name: string
  description: string
  severity: string
  normative_source: string
  required_evidence_types: string[]
  conditions: RuleTemplateCondition[]
  justification: string
  corrective_action: string
  valid_from: string | null
  valid_to: string | null
  created_at: string
}

export interface RuleAdoption {
  adoption_id: string
  organization_id: string
  rule_identity_id: string
  rule_version_id: string
  purpose: string
  scope: string
  adopted_at: string
  reason: string
  status: string
}

export interface ExecutedGovernanceFlow {
  template_code: string
  identity: RuleIdentity
  version: RuleVersion
  adoption: RuleAdoption | null
}

export function executeGovernanceFlow(
  options: RequestOptions,
  templateCode: string,
  params: GovernanceFlowParams & { policyId: string; createAdoption: boolean },
): Promise<ExecutedGovernanceFlow> {
  return chamar<ExecutedGovernanceFlow>(
    `/v1/rule-governance/catalogs/livestock-market-rules/templates/${templateCode}/execute`,
    options,
    {
      method: 'POST',
      body: JSON.stringify({
        policy_id: params.policyId,
        market_purpose: params.marketPurpose,
        adoption_scope: params.adoptionScope,
        name: params.name,
        normative_source: params.normativeSource ?? '',
        version_description: params.versionDescription ?? '',
        adoption_reason: params.adoptionReason ?? '',
        create_adoption: params.createAdoption,
        parameters: params.parameters,
      }),
    },
  )
}
