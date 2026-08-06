import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  AnimalApiError,
  fetchAnimal,
  fetchProperty,
  type AnimalResumo,
  type PropriedadeResumo,
} from '../api/animals'

interface Options {
  baseUrl: string
  accessToken: string
  organizationId: string
}

// Tela S3 (LIV-PROD-01): hub operacional do animal. Mostra a propriedade de
// NASCIMENTO (é o único vínculo com propriedade que o backend expõe hoje) —
// deliberadamente rotulada como tal, e não como "onde o animal está agora":
// a estadia atual (PropertyStay) ainda não tem leitura HTTP própria. Ver
// docs/plans/LIVESTOCK_PRODUCT_EXECUTION_PACKAGE.md, seção de gap aceito.
export function AnimalDetail(options: Options) {
  const { animalId } = useParams<{ animalId: string }>()
  const [animal, setAnimal] = useState<AnimalResumo | null>(null)
  const [propriedade, setPropriedade] = useState<PropriedadeResumo | null>(null)
  const [naoEncontrado, setNaoEncontrado] = useState(false)
  const [semPermissao, setSemPermissao] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  useEffect(() => {
    if (!animalId) return
    let cancelado = false
    setErro(null)
    setNaoEncontrado(false)
    setSemPermissao(false)
    setAnimal(null)
    setPropriedade(null)

    fetchAnimal(options, animalId)
      .then((encontrado) => {
        if (cancelado) return
        setAnimal(encontrado)
        if (encontrado.birth_property_id) {
          fetchProperty(options, encontrado.birth_property_id)
            .then((prop) => {
              if (!cancelado) setPropriedade(prop)
            })
            .catch(() => {
              // A propriedade de nascimento é informação auxiliar: se a
              // leitura falhar, o detalhe do animal continua útil sem ela.
            })
        }
      })
      .catch((error: unknown) => {
        if (cancelado) return
        if (error instanceof AnimalApiError && error.status === 403) {
          setSemPermissao(true)
          return
        }
        if (error instanceof AnimalApiError && error.status === 404) {
          setNaoEncontrado(true)
          return
        }
        setErro(error instanceof Error ? error.message : 'Falha ao carregar o animal.')
      })
    return () => {
      cancelado = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options.baseUrl, options.accessToken, options.organizationId, animalId])

  if (semPermissao) {
    return <p role="alert">Você não tem permissão para ler animais nesta Organization.</p>
  }
  if (naoEncontrado) {
    return <p role="alert">Animal não encontrado nesta Organization.</p>
  }
  if (erro) {
    return <p role="alert">{erro}</p>
  }
  if (!animal) {
    return <p>Carregando…</p>
  }

  return (
    <section>
      <p>
        <Link to="/animals">&larr; Voltar para a busca</Link>
      </p>
      <h2>Animal {animal.animal_id}</h2>
      <dl>
        <dt>Sexo</dt>
        <dd>{animal.sex}</dd>
        <dt>Raça</dt>
        <dd>{animal.breed ?? '—'}</dd>
        <dt>Data de nascimento</dt>
        <dd>{animal.birth_date ?? 'desconhecida'}</dd>
        <dt>Propriedade de nascimento</dt>
        <dd>
          {propriedade
            ? `${propriedade.name} (${propriedade.municipality}/${propriedade.state_code})`
            : (animal.birth_property_id ?? 'não determinável')}
        </dd>
        <dt>Localização atual</dt>
        <dd>
          <em>não disponível nesta versão</em>
        </dd>
        <dt>Identificadores</dt>
        <dd>
          {animal.identifiers.length === 0
            ? 'nenhum'
            : animal.identifiers.map((id) => `${id.type}: ${id.value} (${id.state})`).join(', ')}
        </dd>
        {animal.saida && (
          <>
            <dt>Saída do rebanho</dt>
            <dd>
              {animal.saida.exit_type} em{' '}
              {new Date(animal.saida.occurred_at).toLocaleDateString('pt-BR')}
            </dd>
          </>
        )}
      </dl>

      <h3>Ações</h3>
      <ul>
        <li>
          <Link to={`/animals/${animal.animal_id}/timeline`}>Ver timeline</Link>
        </li>
        <li>
          <Link to={`/animals/${animal.animal_id}/treatments/new`}>Registrar tratamento</Link>
        </li>
        <li>
          <Link to={`/animals/${animal.animal_id}/eligibility`}>Executar elegibilidade</Link>
        </li>
        <li>
          <Link to={`/animals/${animal.animal_id}/market-matrix`}>Executar análise de mercado</Link>
        </li>
      </ul>
    </section>
  )
}
