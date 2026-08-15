import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { LotApiError, fetchLots, type LoteAnimaisResumo } from '../api/lots'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  UnauthorizedState,
} from '../components/AsyncStates'

interface Options {
  baseUrl: string
  accessToken: string
  organizationId: string
}

const TAMANHO_DA_PAGINA = 20

// Entrada da Onda 4: GET /v1/livestock/lots so lista+pagina, sem filtro de
// busca (diferente de animais) -- lista simples, mesma paginacao de
// AnimalSearch.tsx.
export function LotSearch(options: Options) {
  const [offset, setOffset] = useState(0)
  const [pagina, setPagina] = useState<{ items: LoteAnimaisResumo[]; hasMore: boolean } | null>(
    null,
  )
  const [semPermissao, setSemPermissao] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  useEffect(() => {
    let cancelado = false
    setErro(null)
    fetchLots(options, { limit: TAMANHO_DA_PAGINA, offset })
      .then((resposta) => {
        if (cancelado) return
        setPagina({ items: resposta.items, hasMore: resposta.has_more })
        setSemPermissao(false)
      })
      .catch((error: unknown) => {
        if (cancelado) return
        if (error instanceof LotApiError && error.status === 403) {
          setSemPermissao(true)
          return
        }
        setErro(error instanceof Error ? error.message : 'Falha ao buscar lotes.')
      })
    return () => {
      cancelado = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options.baseUrl, options.accessToken, options.organizationId, offset])

  return (
    <section>
      <h2>Buscar lote</h2>

      {semPermissao && (
        <UnauthorizedState
          tone="compact"
          message="Você não tem permissão para ler lotes nesta Organization."
        />
      )}
      {erro && <ErrorState tone="compact" message={erro} />}
      {!semPermissao && !erro && pagina === null && <LoadingState tone="compact" message="Carregando..." />}
      {!semPermissao && !erro && pagina !== null && pagina.items.length === 0 && (
        <EmptyState tone="compact" message="Nenhum lote encontrado." />
      )}
      {!semPermissao && !erro && pagina !== null && pagina.items.length > 0 && (
        <>
          <ul>
            {pagina.items.map((lote) => (
              <li key={lote.lot_id}>
                <Link to={`/lots/${lote.lot_id}`}>
                  {lote.code} — {lote.name} ({lote.lot_type}, {lote.status})
                </Link>
              </li>
            ))}
          </ul>
          <button type="button" onClick={() => setOffset(Math.max(0, offset - TAMANHO_DA_PAGINA))} disabled={offset === 0}>
            Anterior
          </button>{' '}
          <button
            type="button"
            onClick={() => setOffset(offset + TAMANHO_DA_PAGINA)}
            disabled={!pagina.hasMore}
          >
            Próxima
          </button>
        </>
      )}
    </section>
  )
}
