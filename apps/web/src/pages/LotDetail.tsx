import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { LotApiError, fetchLot, fetchLotMembers, type LoteAnimaisResumo, type LotMembership } from '../api/lots'
import {
  EligibilityApiError,
  fetchExternalCounterparties,
  runLotMarketEvaluation,
  type AvaliacaoMercadosLoteResponse,
  type ContraparteExternaResumo,
  type LotMarketEntry,
} from '../api/eligibility'
import {
  ErrorState,
  LoadingState,
  NotFoundState,
  UnauthorizedState,
} from '../components/AsyncStates'
import { DetailDescriptionList, DetailPageHeader, DetailSection } from '../components/DetailPage'

interface Options {
  baseUrl: string
  accessToken: string
  organizationId: string
}

const GRUPOS_POR_STATUS: { chave: keyof LotMarketEntry; rotulo: string }[] = [
  { chave: 'eligible_animal_ids', rotulo: 'Elegíveis' },
  { chave: 'blocked_animal_ids', rotulo: 'Bloqueados' },
  { chave: 'conditioned_animal_ids', rotulo: 'Condicionados' },
  { chave: 'indeterminate_animal_ids', rotulo: 'Indeterminados' },
  { chave: 'missing_animal_ids', rotulo: 'Sem avaliador' },
]

function dependenciaPendente(entry: LotMarketEntry): boolean {
  return entry.dependency !== null && entry.dependency.selected_subject_id === null
}

// Tela S9 (Onda 4): identidade do lote + membros (leitura pura, carrega ao
// montar) + avaliação de mercado do lote (ação explícita, mesmo motivo das
// Ondas 3 -- cada execução é uma leitura agregada real sobre o rebanho, não
// side-effect de navegação).
export function LotDetail(options: Options) {
  const { lotId } = useParams<{ lotId: string }>()
  const [lote, setLote] = useState<LoteAnimaisResumo | null>(null)
  const [membros, setMembros] = useState<LotMembership[] | null>(null)
  const [naoEncontrado, setNaoEncontrado] = useState(false)
  const [semPermissao, setSemPermissao] = useState(false)
  const [erroCarga, setErroCarga] = useState<string | null>(null)

  const [resultado, setResultado] = useState<AvaliacaoMercadosLoteResponse | null>(null)
  const [proposalId, setProposalId] = useState<string | null>(null)
  const [executando, setExecutando] = useState(false)
  const [erroExecucao, setErroExecucao] = useState<string | null>(null)
  const [contrapartes, setContrapartes] = useState<ContraparteExternaResumo[] | null>(null)
  const [contraparteSelecionada, setContraparteSelecionada] = useState('')

  const precisaDeSelecao = resultado?.markets.some(dependenciaPendente) ?? false

  useEffect(() => {
    if (!lotId) return
    let cancelado = false
    setErroCarga(null)
    setNaoEncontrado(false)
    setSemPermissao(false)
    setLote(null)
    setMembros(null)

    fetchLot(options, lotId)
      .then((encontrado) => {
        if (!cancelado) setLote(encontrado)
      })
      .catch((error: unknown) => {
        if (cancelado) return
        if (error instanceof LotApiError && error.status === 403) {
          setSemPermissao(true)
          return
        }
        if (error instanceof LotApiError && error.status === 404) {
          setNaoEncontrado(true)
          return
        }
        setErroCarga(error instanceof Error ? error.message : 'Falha ao carregar o lote.')
      })

    fetchLotMembers(options, lotId)
      .then((resposta) => {
        if (!cancelado) setMembros(resposta.members)
      })
      .catch(() => {
        // A lista de membros é complementar à identidade do lote; se falhar,
        // o restante da tela continua útil.
      })

    return () => {
      cancelado = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options.baseUrl, options.accessToken, options.organizationId, lotId])

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

  if (!lotId) return null

  const executar = async (slaughterhouseCounterpartyId?: string) => {
    setExecutando(true)
    setErroExecucao(null)
    setProposalId(null)
    try {
      const resposta = await runLotMarketEvaluation(options, { lotId, slaughterhouseCounterpartyId })
      setResultado(resposta)
    } catch (error) {
      if (error instanceof EligibilityApiError && error.requiresHumanReview) {
        setProposalId(error.proposalId)
      } else {
        setErroExecucao(
          error instanceof Error ? error.message : 'Falha ao executar a análise de mercado.',
        )
      }
    } finally {
      setExecutando(false)
    }
  }

  if (semPermissao) {
    return (
      <UnauthorizedState
        title="Acesso não autorizado"
        message="Você não tem permissão para ler lotes nesta Organization."
      />
    )
  }
  if (naoEncontrado) {
    return (
      <NotFoundState
        title="Lote não encontrado"
        message="Lote não encontrado nesta Organization."
      />
    )
  }
  if (erroCarga) {
    return <ErrorState title="Falha ao carregar lote" message={erroCarga} />
  }
  if (!lote) {
    return <LoadingState message="Carregando lote..." />
  }

  return (
    <article className="detail-page">
      <DetailPageHeader
        eyebrow="Livestock / Lote"
        title={`Lote ${lote.code}`}
        subtitle="Identidade do lote e operações reais disponíveis para seus membros."
        backTo="/lots"
        backLabel="Voltar para a busca"
        meta={<span className="detail-status-chip">{lote.status}</span>}
      />

      <DetailSection title="Resumo" description="Dados básicos do lote nesta Organization.">
        <DetailDescriptionList>
          <dt>Nome</dt>
          <dd>{lote.name}</dd>
          <dt>Tipo</dt>
          <dd>{lote.lot_type}</dd>
          <dt>Situação</dt>
          <dd>{lote.status}</dd>
          <dt>Membros</dt>
          <dd>
            {membros === null ? (
              'carregando…'
            ) : membros.length === 0 ? (
              'nenhum'
            ) : (
              <>
                {membros.length} animal(is):{' '}
                <ul>
                  {membros.map((membro) => (
                    <li key={membro.membership_id}>
                      <Link to={`/animals/${membro.animal_id}`}>{membro.animal_id}</Link>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </dd>
        </DetailDescriptionList>
      </DetailSection>

      <DetailSection
        title="Análise de mercado do lote"
        description="Execução explícita sobre os membros do lote; não é disparada pela navegação."
      >
        <button type="button" onClick={() => executar()} disabled={executando}>
          {executando ? 'Executando…' : 'Executar análise de mercado do lote'}
        </button>

        {proposalId && (
          <p role="alert">
            Revisão humana necessária antes de emitir a decisão. Proposta:{' '}
            <code>{proposalId}</code>. <Link to={`/review/${proposalId}`}>Abrir revisão humana</Link>
          </p>
        )}
        {erroExecucao && <p role="alert">{erroExecucao}</p>}

        {resultado && (
          <div className="detail-result-block">
            <p>
              <strong>{resultado.commercial_outlook}</strong> — {resultado.executive_summary} (
              {resultado.member_count} membro(s) avaliado(s))
            </p>

            <ul>
              {resultado.markets.map((entry) => (
                <li key={entry.market}>
                  <strong>{entry.market}</strong>: {entry.status}
                  {entry.summary && <> — {entry.summary}</>}
                  <ul>
                    {GRUPOS_POR_STATUS.map(({ chave, rotulo }) => {
                      const animalIds = entry[chave]
                      if (!Array.isArray(animalIds) || animalIds.length === 0) return null
                      return (
                        <li key={chave}>
                          {rotulo} ({animalIds.length}):{' '}
                          {animalIds.map((id, indice) => (
                            <span key={id}>
                              {indice > 0 && ', '}
                              <Link to={`/animals/${id}`}>{id}</Link>
                            </span>
                          ))}
                        </li>
                      )
                    })}
                  </ul>
                </li>
              ))}
            </ul>

            {precisaDeSelecao && (
              <p>
                <label htmlFor="lote-contraparte">
                  Este mercado depende de um estabelecimento ainda não escolhido
                </label>
                <br />
                <select
                  id="lote-contraparte"
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
              <Link to={`/lots/${lotId}/commercial-explanation`}>
                Ver explicação comercial do lote
              </Link>
            </p>
          </div>
        )}
      </DetailSection>
    </article>
  )
}
