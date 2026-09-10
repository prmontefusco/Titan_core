import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { AnimalApiError, fetchAnimalTimeline, type LinhaDoTempoResponse } from '../api/animals'
import { EmptyState, ErrorState, LoadingState, UnauthorizedState } from '../components/AsyncStates'
import { PageContext } from '../components/PageContext'
import { DetailPageHeader, DetailSection } from '../components/DetailPage'

interface Options {
  baseUrl: string
  accessToken: string
  organizationId: string
}

// Tela S5 (LIV-PROD-01): narrativa sanitária histórica, sem reescrever
// história — cada entrada é o que já aconteceu, na ordem em que aconteceu.
export function AnimalTimeline(options: Options) {
  const { animalId } = useParams<{ animalId: string }>()
  const [linha, setLinha] = useState<LinhaDoTempoResponse | null>(null)
  const [semPermissao, setSemPermissao] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  useEffect(() => {
    if (!animalId) return
    let cancelado = false
    setErro(null)
    setSemPermissao(false)
    setLinha(null)

    fetchAnimalTimeline(options, animalId)
      .then((resposta) => {
        if (!cancelado) setLinha(resposta)
      })
      .catch((error: unknown) => {
        if (cancelado) return
        if (error instanceof AnimalApiError && error.status === 403) {
          setSemPermissao(true)
          return
        }
        setErro(error instanceof Error ? error.message : 'Falha ao carregar a timeline.')
      })
    return () => {
      cancelado = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options.baseUrl, options.accessToken, options.organizationId, animalId])

  return (
    <article className="detail-page">
      <DetailPageHeader
        eyebrow="Livestock / Timeline"
        title="Timeline do animal"
        subtitle="Eventos históricos devolvidos pela API, sem fundir fontes heterogêneas nem reescrever histórico."
        backTo={animalId ? `/animals/${animalId}` : '/animals'}
        backLabel="Voltar para o animal"
      />
      <PageContext
        description="A narrativa histórica exibida aqui pertence somente ao animal dentro da Organization ativa."
        items={[
          { label: 'Organization', value: options.organizationId },
          { label: 'Animal', value: animalId ?? '—' },
        ]}
      />

      {semPermissao && (
        <UnauthorizedState
          tone="compact"
          message="Você não tem permissão para ler a timeline nesta Organization."
        />
      )}
      {erro && <ErrorState tone="compact" message={erro} />}
      {!semPermissao && !erro && linha === null && <LoadingState tone="compact" message="Carregando..." />}
      {!semPermissao && !erro && linha !== null && linha.entries.length === 0 && (
        <EmptyState tone="compact" message="Nenhum evento registrado ainda." />
      )}
      {!semPermissao && !erro && linha !== null && linha.entries.length > 0 && (
        <DetailSection
          title="Eventos conhecidos"
          description={`${linha.entry_count} evento(s) conhecido(s)${linha.known_until ? ` até ${new Date(linha.known_until).toLocaleString('pt-BR')}` : ''}.`}
        >
          <ol className="animal-timeline-list">
            {linha.entries.map((entrada, indice) => (
              <li key={`${entrada.aggregate_id}-${indice}`}>
                <time dateTime={entrada.occurred_at}>
                  {new Date(entrada.occurred_at).toLocaleString('pt-BR')}
                </time>
                <strong>{entrada.entry_type}</strong>
                <span>{entrada.source_kind} / {entrada.aggregate_type}</span>
                <code>{entrada.aggregate_id}</code>
                {entrada.superseded_by && <em>Substituído por {entrada.superseded_by}</em>}
              </li>
            ))}
          </ol>
        </DetailSection>
      )}
    </article>
  )
}
