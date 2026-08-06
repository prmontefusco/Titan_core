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

interface Options {
  baseUrl: string
  accessToken: string
  organizationId: string
}

function dependenciaPendente(entry: MarketEntry): boolean {
  return entry.dependency !== null && entry.dependency.selected_subject_id === null
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
    <section>
      <p>
        <Link to={`/animals/${animalId}`}>&larr; Voltar para o animal</Link>
      </p>
      <h2>Matriz de mercado</h2>

      <button type="button" onClick={() => executar()} disabled={executando}>
        {executando ? 'Executando…' : 'Executar análise de mercado'}
      </button>

      {proposalId && (
        <p role="alert">
          Revisão humana necessária antes de emitir a decisão. Proposta: <code>{proposalId}</code>.{' '}
          <Link to={`/review/${proposalId}`}>Abrir revisão humana</Link>
        </p>
      )}
      {erro && <p role="alert">{erro}</p>}

      {resultado && (
        <>
          <p>
            <strong>{resultado.commercial_outlook}</strong> — {resultado.executive_summary}
          </p>

          <ul>
            {resultado.markets.map((entry) => (
              <li key={entry.market}>
                <strong>{entry.market}</strong>: {entry.status}
                {entry.summary && <> — {entry.summary}</>}
                {entry.gaps.length > 0 && (
                  <ul>
                    {entry.gaps.map((gap, indice) => (
                      <li key={indice}>{gap.message}</li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>

          {precisaDeSelecao && (
            <p>
              <label htmlFor="matriz-contraparte">
                Este mercado depende de um estabelecimento ainda não escolhido
              </label>
              <br />
              <select
                id="matriz-contraparte"
                value={contraparteSelecionada}
                onChange={(evento) => setContraparteSelecionada(evento.target.value)}
              >
                <option value="">
                  {contrapartes === null ? 'Carregando…' : 'Selecione um estabelecimento'}
                </option>
                {contrapartes?.map((contraparte) => (
                  <option key={contraparte.counterparty_id} value={contraparte.counterparty_id}>
                    {contraparte.name}
                  </option>
                ))}
              </select>{' '}
              <button
                type="button"
                onClick={() => executar(contraparteSelecionada)}
                disabled={!contraparteSelecionada || executando}
              >
                Reavaliar com estabelecimento selecionado
              </button>
            </p>
          )}

          <p>
            <Link to={`/animals/${animalId}/commercial-explanation`}>Ver explicação comercial</Link>
          </p>
        </>
      )}
    </section>
  )
}
