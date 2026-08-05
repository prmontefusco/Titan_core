import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { AnimalApiError, fetchAnimalTimeline, type LinhaDoTempoResponse } from '../api/animals'

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
    <section>
      <p>
        <Link to={animalId ? `/animals/${animalId}` : '/animals'}>&larr; Voltar para o animal</Link>
      </p>
      <h2>Timeline do animal {animalId}</h2>

      {semPermissao && (
        <p role="alert">Você não tem permissão para ler a timeline nesta Organization.</p>
      )}
      {erro && <p role="alert">{erro}</p>}
      {!semPermissao && !erro && linha === null && <p>Carregando…</p>}
      {!semPermissao && !erro && linha !== null && linha.entries.length === 0 && (
        <p>Nenhum evento registrado ainda.</p>
      )}
      {!semPermissao && !erro && linha !== null && linha.entries.length > 0 && (
        <ul>
          {linha.entries.map((entrada, indice) => (
            <li key={`${entrada.aggregate_id}-${indice}`}>
              {new Date(entrada.occurred_at).toLocaleString('pt-BR')} — {entrada.entry_type} (
              {entrada.source_kind})
              {entrada.superseded_by && <> — substituído por {entrada.superseded_by}</>}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
