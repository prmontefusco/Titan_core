import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  EligibilityApiError,
  fetchExternalCounterparties,
  runMarketEvaluation,
  type AvaliacaoMercadosResponse,
  type ContraparteExternaResumo,
  type MarketEntry,
} from '../api/eligibility'
import { ErrorState } from '../components/AsyncStates'
import { DetailPageHeader, DetailSection } from '../components/DetailPage'
import { PageContext } from '../components/PageContext'

interface Options {
  baseUrl: string
  accessToken: string
  organizationId: string
}

function dependenciaPendente(entry: MarketEntry): boolean {
  return entry.dependency !== null && entry.dependency.selected_subject_id === null
}

function textosUnicos(textos: string[]): string[] {
  return [...new Set(textos)]
}

// Tela S7 (Onda 3). Quando algum mercado depende de um sujeito ainda não
// escolhido (ex.: China exige frigorífico), mostra o seletor e reexecuta com
// slaughterhouse_counterparty_id -- o backend não aceita mapear dependência
// por mercado, só um sujeito por chamada (contrato atual de
// POST /market-eligibility/evaluations).
export function MarketMatrix(options: Options) {
  const { animalId } = useParams<{ animalId: string }>()
  const [resultado, setResultado] = useState<AvaliacaoMercadosResponse | null>(null)
  const [proposalId, setProposalId] = useState<string | null>(null)
  const [executando, setExecutando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [contrapartes, setContrapartes] = useState<ContraparteExternaResumo[] | null>(null)
  const [contraparteSelecionada, setContraparteSelecionada] = useState('')

  const precisaDeSelecao = resultado?.markets.some(dependenciaPendente) ?? false

  useEffect(() => {
    if (!precisaDeSelecao || contrapartes !== null) return
    fetchExternalCounterparties(options)
      .then((resposta) =>
        setContrapartes(
          resposta.items.filter((item) => item.counterparty_type === 'SLAUGHTERHOUSE'),
        ),
      )
      .catch(() => setContrapartes([]))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [precisaDeSelecao, contrapartes])

  if (!animalId) return null

  const executar = async (slaughterhouseCounterpartyId?: string) => {
    setExecutando(true)
    setErro(null)
    setProposalId(null)
    try {
      const resposta = await runMarketEvaluation(options, { animalId, slaughterhouseCounterpartyId })
      setResultado(resposta)
    } catch (error) {
      if (error instanceof EligibilityApiError && error.requiresHumanReview) {
        setProposalId(error.proposalId)
      } else {
        setErro(error instanceof Error ? error.message : 'Falha ao executar a análise de mercado.')
      }
    } finally {
      setExecutando(false)
    }
  }

  return (
    <article className="detail-page">
      <DetailPageHeader
        eyebrow="Livestock / Mercado"
        title="Matriz de mercado"
        subtitle="Avaliação comercial por mercado devolvida pela API. A UI não recalcula elegibilidade nem resolve dependências por conta própria."
        backTo={`/animals/${animalId}`}
        backLabel="Voltar para o animal"
        actions={
          <button type="button" onClick={() => executar()} disabled={executando}>
            {executando ? 'Executando...' : 'Executar análise de mercado'}
          </button>
        }
      />

      <PageContext
        description="A análise usa o animal e a Organization ativa. Dependências comerciais continuam explícitas quando a API exigir sujeito adicional."
        items={[
          { label: 'Organization', value: options.organizationId },
          { label: 'Animal', value: animalId },
        ]}
      />

      {proposalId && (
        <section className="eligibility-review-alert" role="alert">
          <h2>Revisão humana necessária</h2>
          <p>A API recusou a emissão automática. Proposta: <code>{proposalId}</code>.</p>
          <Link to={`/review/${proposalId}`}>Abrir revisão humana</Link>
        </section>
      )}
      {erro && <ErrorState tone="compact" title="Falha ao executar análise" message={erro} />}

      {!resultado && !proposalId && !erro && (
        <DetailSection
          title="Antes de executar"
          description="A análise só é solicitada quando o operador executa a ação explicitamente."
        >
          <p className="empty-notice">
            Execute a matriz para ver mercados elegíveis, bloqueados, condicionados ou indeterminados.
          </p>
        </DetailSection>
      )}

      {resultado && (
        <DetailSection
          title="Resultado comercial"
          description="Conclusão e mercados retornados pelo backend para esta execução."
        >
          <div className="market-flow-summary">
            <span className="detail-status-chip">{resultado.commercial_outlook}</span>
            <p>{resultado.executive_summary}</p>
            <Link to={`/animals/${animalId}/commercial-explanation`}>Ver explicação comercial</Link>
          </div>

          <ul className="market-flow-list">
            {resultado.markets.map((entry) => (
              <li key={entry.market}>
                <div>
                  <strong>{entry.market}</strong>
                  <span className="market-status-chip">{entry.status}</span>
                </div>
                {entry.summary && <p>{entry.summary}</p>}
                {entry.gaps.length > 0 && (
                  <ul>
                    {textosUnicos(entry.gaps.map((gap) => gap.message)).map((mensagem) => (
                      <li key={mensagem}>{mensagem}</li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>

          {precisaDeSelecao && (
            <div className="market-dependency-box">
              <label htmlFor="matriz-contraparte">
                Este mercado depende de um estabelecimento ainda não escolhido
              </label>
              <select
                id="matriz-contraparte"
                value={contraparteSelecionada}
                onChange={(evento) => setContraparteSelecionada(evento.target.value)}
              >
                <option value="">
                  {contrapartes === null ? 'Carregando...' : 'Selecione um estabelecimento'}
                </option>
                {contrapartes?.map((contraparte) => (
                  <option key={contraparte.counterparty_id} value={contraparte.counterparty_id}>
                    {contraparte.name}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => executar(contraparteSelecionada)}
                disabled={!contraparteSelecionada || executando}
              >
                Reavaliar com estabelecimento selecionado
              </button>
            </div>
          )}
        </DetailSection>
      )}
    </article>
  )
}
