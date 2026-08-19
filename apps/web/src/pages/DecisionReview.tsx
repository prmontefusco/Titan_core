import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  DecisionReviewApiError,
  fetchDossier,
  fetchProposal,
  submitReview,
  type DecisionProposalResponse,
  type DecisionReviewExecutionResponse,
  type DossierResponse,
  type ReviewConclusion,
} from '../api/decisionReview'
import { ErrorState, LoadingState, NotFoundState } from '../components/AsyncStates'
import { PageContext } from '../components/PageContext'

interface Options {
  baseUrl: string
  accessToken: string
  organizationId: string
}

const CONCLUSOES: { valor: ReviewConclusion; rotulo: string }[] = [
  { valor: 'APROVA', rotulo: 'Aprovar' },
  { valor: 'REJEITA', rotulo: 'Rejeitar' },
  { valor: 'DEVOLVE', rotulo: 'Devolver para nova proposta' },
]

const STATUS_ROTULO: Record<string, string> = {
  REVIEW_RECORDED: 'Revisão registrada.',
  AGUARDANDO_APROVACOES: 'Revisão registrada — aguardando mais aprovações.',
  DECISION_EMITTED: 'Decisão emitida.',
}

// Tela S10 (Onda 5, última leva): destino real dos avisos de
// REVISAO_HUMANA_NECESSARIA nas telas de elegibilidade/mercado/explicação
// comercial. GET .../decision-proposals/{id} é leitura pura (carrega ao
// montar, como a identidade em LotDetail.tsx); registrar revisão continua
// ação explícita, mesma razão das Ondas 3/4.
export function DecisionReview(options: Options) {
  const { proposalId } = useParams<{ proposalId: string }>()
  const [proposta, setProposta] = useState<DecisionProposalResponse | null>(null)
  const [naoEncontrada, setNaoEncontrada] = useState(false)
  const [erroCarga, setErroCarga] = useState<string | null>(null)

  const [conclusion, setConclusion] = useState<ReviewConclusion>('APROVA')
  const [reasoning, setReasoning] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [erroEnvio, setErroEnvio] = useState<string | null>(null)
  const [resultado, setResultado] = useState<DecisionReviewExecutionResponse | null>(null)

  const [dossie, setDossie] = useState<DossierResponse | null>(null)
  const [carregandoDossie, setCarregandoDossie] = useState(false)
  const [erroDossie, setErroDossie] = useState<string | null>(null)

  useEffect(() => {
    if (!proposalId) return
    let cancelado = false
    setErroCarga(null)
    setNaoEncontrada(false)
    setProposta(null)

    fetchProposal(options, proposalId)
      .then((encontrada) => {
        if (!cancelado) setProposta(encontrada)
      })
      .catch((error: unknown) => {
        if (cancelado) return
        if (error instanceof DecisionReviewApiError && error.status === 404) {
          setNaoEncontrada(true)
          return
        }
        setErroCarga(error instanceof Error ? error.message : 'Falha ao carregar a proposta.')
      })

    return () => {
      cancelado = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options.baseUrl, options.accessToken, options.organizationId, proposalId])

  if (!proposalId) return null

  const registrarRevisao = async () => {
    setEnviando(true)
    setErroEnvio(null)
    try {
      const resposta = await submitReview(options, proposalId, { conclusion, reasoning })
      setResultado(resposta)
    } catch (error) {
      setErroEnvio(error instanceof Error ? error.message : 'Falha ao registrar a revisão.')
    } finally {
      setEnviando(false)
    }
  }

  const abrirDossie = async (dossierId: string) => {
    setCarregandoDossie(true)
    setErroDossie(null)
    try {
      const encontrado = await fetchDossier(options, dossierId)
      setDossie(encontrado)
    } catch (error) {
      setErroDossie(error instanceof Error ? error.message : 'Falha ao abrir o dossiê.')
    } finally {
      setCarregandoDossie(false)
    }
  }

  if (naoEncontrada) {
    return <NotFoundState message="Proposta não encontrada nesta Organization." />
  }
  if (erroCarga) {
    return <ErrorState message={erroCarga} />
  }
  if (!proposta) {
    return <LoadingState message="Carregando..." />
  }

  return (
    <section>
      <h2>Revisão humana de decisão</h2>
      <PageContext
        description="A revisão atua somente sobre a proposta e a finalidade autorizadas dentro da Organization ativa."
        items={[
          { label: 'Organization', value: options.organizationId },
          { label: 'Proposta', value: proposalId },
          { label: 'Finalidade', value: proposta.purpose },
        ]}
      />
      <dl>
        <dt>Finalidade</dt>
        <dd>{proposta.purpose}</dd>
        <dt>Resultado proposto</dt>
        <dd>{proposta.proposed_result}</dd>
        <dt>Motivos propostos</dt>
        <dd>
          {proposta.proposed_reasons.length === 0 ? (
            'nenhum'
          ) : (
            <ul>
              {proposta.proposed_reasons.map((motivo, indice) => (
                <li key={indice}>{motivo.message ?? JSON.stringify(motivo)}</li>
              ))}
            </ul>
          )}
        </dd>
        <dt>Fundamentação exigida</dt>
        <dd>{proposta.justification_required ? 'sim' : 'não'}</dd>
        <dt>Criada em</dt>
        <dd>{proposta.created_at}</dd>
        <dt>Revisões registradas</dt>
        <dd>{proposta.review_count}</dd>
        <dt>Atualidade</dt>
        <dd>
          {proposta.current_proposal
            ? 'Esta é a proposta corrente.'
            : 'Superada por uma proposta mais recente.'}
        </dd>
      </dl>

      {!resultado && (
        <>
          <h3>Registrar revisão</h3>
          <p>
            <label htmlFor="revisao-conclusao">Conclusão</label>
            <br />
            <select
              id="revisao-conclusao"
              value={conclusion}
              onChange={(evento) => setConclusion(evento.target.value as ReviewConclusion)}
            >
              {CONCLUSOES.map((opcao) => (
                <option key={opcao.valor} value={opcao.valor}>
                  {opcao.rotulo}
                </option>
              ))}
            </select>
          </p>
          <p>
            <label htmlFor="revisao-fundamentacao">Fundamentação</label>
            <br />
            <textarea
              id="revisao-fundamentacao"
              value={reasoning}
              onChange={(evento) => setReasoning(evento.target.value)}
              rows={4}
            />
          </p>
          <button
            type="button"
            onClick={registrarRevisao}
            disabled={enviando || reasoning.trim().length === 0}
          >
            {enviando ? 'Registrando…' : 'Registrar revisão'}
          </button>
          {erroEnvio && <p role="alert">{erroEnvio}</p>}
        </>
      )}

      {resultado && (
        <>
          <h3>Resultado</h3>
          <p>{STATUS_ROTULO[resultado.workflow_status] ?? resultado.workflow_status}</p>
          {resultado.decision_id && (
            <p>
              Decisão: <code>{resultado.decision_id}</code>
            </p>
          )}
          {resultado.dossier_id && (
            <p>
              <button
                type="button"
                onClick={() => abrirDossie(resultado.dossier_id!)}
                disabled={carregandoDossie}
              >
                {carregandoDossie ? 'Abrindo…' : 'Abrir dossiê'}
              </button>
            </p>
          )}
          {erroDossie && <p role="alert">{erroDossie}</p>}
          {dossie && (
            <div>
              <dl>
                <dt>Dossiê</dt>
                <dd>
                  <code>{dossie.dossier_id}</code>
                </dd>
                <dt>Hash</dt>
                <dd>
                  <code>{dossie.dossier_hash}</code>
                </dd>
                <dt>Gerado em</dt>
                <dd>{dossie.generated_at}</dd>
              </dl>
              <pre>{JSON.stringify(dossie.document, null, 2)}</pre>
            </div>
          )}
        </>
      )}
    </section>
  )
}
