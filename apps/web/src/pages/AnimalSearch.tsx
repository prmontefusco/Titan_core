import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { AnimalApiError, fetchAnimals, type AnimalResumo } from '../api/animals'
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

// Tela S2 (LIV-PROD-01): encontrar um animal específico num rebanho grande.
// O filtro por identificador usa o parâmetro `identifier` do backend (busca
// por trecho, sem distinguir tipo de identificador).
export function AnimalSearch(options: Options) {
  const [termo, setTermo] = useState('')
  const [filtroAtivo, setFiltroAtivo] = useState('')
  const [offset, setOffset] = useState(0)
  const [pagina, setPagina] = useState<{ items: AnimalResumo[]; hasMore: boolean } | null>(null)
  const [semPermissao, setSemPermissao] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  useEffect(() => {
    let cancelado = false
    setErro(null)
    fetchAnimals(options, { identifier: filtroAtivo || undefined, limit: TAMANHO_DA_PAGINA, offset })
      .then((resposta) => {
        if (cancelado) return
        setPagina({ items: resposta.items, hasMore: resposta.has_more })
        setSemPermissao(false)
      })
      .catch((error: unknown) => {
        if (cancelado) return
        if (error instanceof AnimalApiError && error.status === 403) {
          setSemPermissao(true)
          return
        }
        setErro(error instanceof Error ? error.message : 'Falha ao buscar animais.')
      })
    return () => {
      cancelado = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options.baseUrl, options.accessToken, options.organizationId, filtroAtivo, offset])

  const buscar = (evento: FormEvent) => {
    evento.preventDefault()
    setOffset(0)
    setFiltroAtivo(termo.trim())
  }

  return (
    <section>
      <h2>Buscar animal</h2>
      <form onSubmit={buscar}>
        <label htmlFor="busca-identificador">Identificador (trecho do valor)</label>{' '}
        <input
          id="busca-identificador"
          type="text"
          value={termo}
          onChange={(evento) => setTermo(evento.target.value)}
          placeholder="ex.: BR9988"
        />{' '}
        <button type="submit">Buscar</button>
      </form>

      {semPermissao && (
        <UnauthorizedState
          tone="compact"
          message="Você não tem permissão para ler animais nesta Organization."
        />
      )}
      {erro && <ErrorState tone="compact" message={erro} />}
      {!semPermissao && !erro && pagina === null && <LoadingState tone="compact" message="Carregando..." />}
      {!semPermissao && !erro && pagina !== null && pagina.items.length === 0 && (
        <EmptyState
          tone="compact"
          message={`Nenhum animal encontrado${filtroAtivo ? ` para "${filtroAtivo}"` : ''}.`}
        />
      )}
      {!semPermissao && !erro && pagina !== null && pagina.items.length > 0 && (
        <>
          <ul>
            {pagina.items.map((animal) => (
              <li key={animal.animal_id}>
                <Link to={`/animals/${animal.animal_id}`}>
                  {animal.identifiers[0]?.value ?? animal.animal_id} — {animal.sex}
                  {animal.breed ? `, ${animal.breed}` : ''}
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
