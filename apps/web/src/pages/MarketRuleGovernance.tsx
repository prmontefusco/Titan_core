import { useEffect, useState } from 'react'
import {
  PolicyGovernanceApiError,
  createPolicy,
  executeGovernanceFlow,
  fetchMarketRuleCatalog,
  listPolicies,
  publishPolicy,
  suggestGovernanceFlow,
  type ExecutedGovernanceFlow,
  type LivestockMarketRuleCatalog,
  type PolicyResponse,
  type SuggestedGovernanceFlow,
} from '../api/policyGovernance'

interface Options {
  baseUrl: string
  accessToken: string
  organizationId: string
}

// Incremento 2 (NR-5): tela sobre a API do Incremento 1
// (apps/api/policy_governance.py + livestock_rule_governance.py). Não
// inventa lógica nova — só guia o operador pelos mesmos quatro passos que a
// API já expõe: escolher/publicar a Policy, escolher o template, pré-ver o
// que seria criado (sem gravar nada) e só então confirmar.
export function MarketRuleGovernance(options: Options) {
  const [catalogo, setCatalogo] = useState<LivestockMarketRuleCatalog | null>(null)
  const [semPermissaoCatalogo, setSemPermissaoCatalogo] = useState(false)
  const [erroCatalogo, setErroCatalogo] = useState<string | null>(null)

  const [policies, setPolicies] = useState<PolicyResponse[] | null>(null)
  const [erroPolicies, setErroPolicies] = useState<string | null>(null)
  const [policyId, setPolicyId] = useState('')

  const [novoCodigo, setNovoCodigo] = useState('')
  const [novoNome, setNovoNome] = useState('')
  const [criandoPolicy, setCriandoPolicy] = useState(false)
  const [erroPolicyForm, setErroPolicyForm] = useState<string | null>(null)
  const [publicandoId, setPublicandoId] = useState<string | null>(null)

  const [templateCode, setTemplateCode] = useState('')
  const [parametros, setParametros] = useState<Record<string, string>>({})
  const [marketPurpose, setMarketPurpose] = useState('')
  const [adoptionScope, setAdoptionScope] = useState('livestock.animal')
  const [nome, setNome] = useState('')
  const [normativeSource, setNormativeSource] = useState('')

  const [previa, setPrevia] = useState<SuggestedGovernanceFlow | null>(null)
  const [carregandoPrevia, setCarregandoPrevia] = useState(false)
  const [erroPrevia, setErroPrevia] = useState<string | null>(null)

  const [resultado, setResultado] = useState<ExecutedGovernanceFlow | null>(null)
  const [executando, setExecutando] = useState(false)
  const [erroExecucao, setErroExecucao] = useState<string | null>(null)

  const recarregarPolicies = () => {
    setErroPolicies(null)
    listPolicies(options)
      .then((pagina) => setPolicies(pagina.items))
      .catch((error: unknown) =>
        setErroPolicies(error instanceof Error ? error.message : 'Falha ao listar políticas.'),
      )
  }

  useEffect(() => {
    setErroCatalogo(null)
    setSemPermissaoCatalogo(false)
    fetchMarketRuleCatalog(options)
      .then(setCatalogo)
      .catch((error: unknown) => {
        if (error instanceof PolicyGovernanceApiError && error.status === 403) {
          setSemPermissaoCatalogo(true)
          return
        }
        setErroCatalogo(error instanceof Error ? error.message : 'Falha ao carregar o catálogo.')
      })
    recarregarPolicies()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options.baseUrl, options.accessToken, options.organizationId])

  const template = catalogo?.templates.find((item) => item.template_code === templateCode) ?? null

  const criarPolicy = async () => {
    setCriandoPolicy(true)
    setErroPolicyForm(null)
    try {
      const criada = await createPolicy(options, { code: novoCodigo, name: novoNome })
      setNovoCodigo('')
      setNovoNome('')
      setPolicyId(criada.policy_id)
      recarregarPolicies()
    } catch (error) {
      setErroPolicyForm(error instanceof Error ? error.message : 'Falha ao criar a política.')
    } finally {
      setCriandoPolicy(false)
    }
  }

  const publicar = async (id: string) => {
    setPublicandoId(id)
    setErroPolicyForm(null)
    try {
      await publishPolicy(options, id)
      recarregarPolicies()
    } catch (error) {
      setErroPolicyForm(error instanceof Error ? error.message : 'Falha ao publicar a política.')
    } finally {
      setPublicandoId(null)
    }
  }

  const camposDoFluxoCompletos =
    templateCode.length > 0 &&
    marketPurpose.trim().length > 0 &&
    adoptionScope.trim().length > 0 &&
    nome.trim().length > 0 &&
    (template?.parameters ?? []).every((parametro) => (parametros[parametro.name] ?? '').trim())

  const gerarPrevia = async () => {
    setCarregandoPrevia(true)
    setErroPrevia(null)
    setPrevia(null)
    try {
      const sugestao = await suggestGovernanceFlow(options, templateCode, {
        marketPurpose,
        adoptionScope,
        name: nome,
        normativeSource,
        parameters: parametros,
      })
      setPrevia(sugestao)
    } catch (error) {
      setErroPrevia(error instanceof Error ? error.message : 'Falha ao pré-visualizar o fluxo.')
    } finally {
      setCarregandoPrevia(false)
    }
  }

  const confirmar = async () => {
    setExecutando(true)
    setErroExecucao(null)
    try {
      const executado = await executeGovernanceFlow(options, templateCode, {
        marketPurpose,
        adoptionScope,
        name: nome,
        normativeSource,
        parameters: parametros,
        policyId,
        createAdoption: true,
      })
      setResultado(executado)
    } catch (error) {
      setErroExecucao(error instanceof Error ? error.message : 'Falha ao confirmar o fluxo.')
    } finally {
      setExecutando(false)
    }
  }

  if (semPermissaoCatalogo) {
    return <p>Você não tem permissão para administrar regras de mercado nesta Organization.</p>
  }
  if (erroCatalogo) {
    return <p role="alert">{erroCatalogo}</p>
  }
  if (!catalogo) {
    return <p>Carregando…</p>
  }

  return (
    <section>
      <h2>Regras de mercado</h2>
      <p>
        Escolha ou publique a política, escolha um modelo de regra já classificado, pré-visualize
        o que seria criado e só então confirme.
      </p>

      <h3>1. Política (Policy)</h3>
      <p>
        Uma política agrupa regras relacionadas — por exemplo, todas as exigências de um mercado
        ou uma política interna do frigorífico. Toda regra publicada abaixo pertence a uma
        política.
      </p>
      {erroPolicies && <p role="alert">{erroPolicies}</p>}
      {policies && policies.length > 0 && (
        <p>
          <label htmlFor="policy-existente">Usar política existente</label>
          <br />
          <select
            id="policy-existente"
            value={policyId}
            onChange={(evento) => setPolicyId(evento.target.value)}
          >
            <option value="">— selecione —</option>
            {policies.map((item) => (
              <option key={item.policy_id} value={item.policy_id}>
                {item.code} v{item.version} ({item.status})
              </option>
            ))}
          </select>
          {policyId &&
            policies.find((item) => item.policy_id === policyId)?.status === 'draft' && (
              <>
                {' '}
                <button
                  type="button"
                  onClick={() => publicar(policyId)}
                  disabled={publicandoId === policyId}
                >
                  {publicandoId === policyId ? 'Publicando…' : 'Publicar esta política'}
                </button>
              </>
            )}
        </p>
      )}

      <p>Ou crie uma nova (nasce como rascunho):</p>
      <p>
        <label htmlFor="novo-policy-codigo">Código</label>
        <br />
        <small>
          Identificador estável, minúsculo, sem espaço — não muda depois de criado (ex.:
          politica-mercado-interno).
        </small>
        <br />
        <input
          id="novo-policy-codigo"
          value={novoCodigo}
          onChange={(evento) => setNovoCodigo(evento.target.value)}
          placeholder="ex.: politica-mercado-interno"
        />
      </p>
      <p>
        <label htmlFor="novo-policy-nome">Nome</label>
        <br />
        <small>Nome legível, para reconhecer esta política nas listagens.</small>
        <br />
        <input
          id="novo-policy-nome"
          value={novoNome}
          onChange={(evento) => setNovoNome(evento.target.value)}
          placeholder="ex.: Política de Mercado Interno"
        />
      </p>
      <button
        type="button"
        onClick={criarPolicy}
        disabled={criandoPolicy || !novoCodigo.trim() || !novoNome.trim()}
      >
        {criandoPolicy ? 'Criando…' : 'Criar política'}
      </button>
      {erroPolicyForm && <p role="alert">{erroPolicyForm}</p>}

      <h3>2. Modelo de regra (template)</h3>
      <p>
        Cada modelo já traz pronta a verificação técnica que ele faz — o <code>fact_type</code> é
        o dado que o Titan já sabe calcular (carência, embargo ambiental, campanha sanitária
        etc.) e que a regra vai conferir. Você não escreve isso; só escolhe o modelo e preenche os
        parâmetros que ele pedir.
      </p>
      <p>
        <label htmlFor="template-select">Modelo</label>
        <br />
        <select
          id="template-select"
          value={templateCode}
          onChange={(evento) => {
            setTemplateCode(evento.target.value)
            setParametros({})
            setPrevia(null)
          }}
        >
          <option value="">— selecione —</option>
          {catalogo.templates.map((item) => (
            <option key={item.template_code} value={item.template_code}>
              {item.name}
            </option>
          ))}
        </select>
      </p>
      {template && (
        <>
          <p>{template.purpose_hint}</p>
          {template.parameters.map((parametro) => (
            <p key={parametro.name}>
              <label htmlFor={`param-${parametro.name}`}>
                {parametro.description} (ex.: {parametro.example})
              </label>
              <br />
              <input
                id={`param-${parametro.name}`}
                value={parametros[parametro.name] ?? ''}
                onChange={(evento) =>
                  setParametros({ ...parametros, [parametro.name]: evento.target.value })
                }
              />
            </p>
          ))}
        </>
      )}

      <h3>3. Mercado e identificação</h3>
      <p>
        Estes campos dizem para qual finalidade a regra vale e como ela vai aparecer depois — não
        existe uma lista fixa de valores permitidos, você escolhe e reaproveita os mesmos daqui em
        diante.
      </p>
      <p>
        <label htmlFor="market-purpose">Mercado (purpose)</label>
        <br />
        <small>
          Chave que identifica a finalidade — é o valor de <code>market_purpose</code> que depois
          aparece nas consultas de elegibilidade. Escolha algo estável e reconhecível.
        </small>
        <br />
        <input
          id="market-purpose"
          value={marketPurpose}
          onChange={(evento) => setMarketPurpose(evento.target.value)}
          placeholder="ex.: mercado-interno, exportacao-china"
        />
      </p>
      <p>
        <label htmlFor="adoption-scope">Escopo de adoção</label>
        <br />
        <small>
          Sobre qual tipo de sujeito a regra atua. Hoje só existe{' '}
          <code>livestock.animal</code> (nível do animal individual) — deixe como está, a menos
          que o modelo escolhido acima peça outro.
        </small>
        <br />
        <input
          id="adoption-scope"
          value={adoptionScope}
          onChange={(evento) => setAdoptionScope(evento.target.value)}
          placeholder="livestock.animal"
        />
      </p>
      <p>
        <label htmlFor="regra-nome">Nome da regra</label>
        <br />
        <small>Nome legível — aparece no dossiê e nas telas de elegibilidade.</small>
        <br />
        <input
          id="regra-nome"
          value={nome}
          onChange={(evento) => setNome(evento.target.value)}
          placeholder="ex.: Carência farmacológica — Mercado Interno"
        />
      </p>
      <p>
        <label htmlFor="fonte-normativa">Fonte normativa</label>
        <br />
        <small>
          De onde vem a exigência — lei, instrução normativa, protocolo do frigorífico ou política
          interna. Texto livre; aparece no dossiê como justificativa.
        </small>
        <br />
        <input
          id="fonte-normativa"
          value={normativeSource}
          onChange={(evento) => setNormativeSource(evento.target.value)}
          placeholder="ex.: Instrução Normativa MAPA nº X, ou 'Política interna do frigorífico'"
        />
      </p>

      <button type="button" onClick={gerarPrevia} disabled={carregandoPrevia || !camposDoFluxoCompletos}>
        {carregandoPrevia ? 'Pré-visualizando…' : 'Pré-visualizar'}
      </button>
      {erroPrevia && <p role="alert">{erroPrevia}</p>}

      {previa && !resultado && (
        <div>
          <h3>Pré-visualização (nada foi gravado)</h3>
          <dl>
            <dt>Identidade</dt>
            <dd>
              {previa.identity.code} — {previa.identity.purpose}
            </dd>
            <dt>Regra</dt>
            <dd>
              {previa.version.name} ({previa.version.severity})
            </dd>
            <dt>Condições</dt>
            <dd>
              <small>
                O que o Titan vai conferir de fato. Sem frase explicativa pronta, aparece o
                formato técnico: fato.campo operador valor-esperado.
              </small>
              <ul>
                {previa.version.conditions.map((condicao, indice) => (
                  <li key={indice}>
                    {condicao.description ||
                      `${condicao.fact_type}.${condicao.payload_key} ${condicao.operator} ${String(condicao.expected_value)}`}
                  </li>
                ))}
              </ul>
            </dd>
            <dt>Adoção</dt>
            <dd>
              {previa.adoption.purpose} / {previa.adoption.scope}
            </dd>
          </dl>
          <button type="button" onClick={confirmar} disabled={executando || !policyId}>
            {executando ? 'Confirmando…' : 'Confirmar e publicar'}
          </button>
          {!policyId && <p role="alert">Escolha ou crie uma política antes de confirmar.</p>}
          {erroExecucao && <p role="alert">{erroExecucao}</p>}
        </div>
      )}

      {resultado && (
        <div>
          <h3>Regra publicada</h3>
          <dl>
            <dt>Identidade da regra</dt>
            <dd>
              <code>{resultado.identity.rule_identity_id}</code>
            </dd>
            <dt>Versão publicada</dt>
            <dd>
              {resultado.version.name} — v{resultado.version.version}
            </dd>
            {resultado.adoption && (
              <>
                <dt>Adoção</dt>
                <dd>
                  {resultado.adoption.purpose} / {resultado.adoption.scope} (
                  {resultado.adoption.status})
                </dd>
              </>
            )}
          </dl>
        </div>
      )}
    </section>
  )
}
