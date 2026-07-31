import { useState, type FormEvent } from 'react'
import { ENTITY_KINDS, type EntityKind } from '../api/entityTypeRequests'
import { ENTITY_KIND_LABELS } from '../entityKinds'

interface Props {
  onSubmit: (kind: EntityKind) => Promise<void>
  negatedReason?: string | null
  defaultKind?: EntityKind
}

export function EntityTypeSelectionForm({ onSubmit, negatedReason, defaultKind }: Props) {
  const [kind, setKind] = useState<EntityKind>(defaultKind ?? 'PRODUTOR')
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setEnviando(true)
    setErro(null)
    try {
      await onSubmit(kind)
    } catch (error) {
      setErro(error instanceof Error ? error.message : 'Não foi possível enviar o pedido.')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <h2>Qual é o seu tipo de entidade?</h2>
      <p>
        Isto é só um pedido — quem administra a Organization precisa aprovar antes de você
        ganhar acesso.
      </p>
      {negatedReason && (
        <p role="alert">Seu pedido anterior foi negado: {negatedReason}</p>
      )}
      {defaultKind && !negatedReason && (
        <p>Pré-selecionamos o que você escolheu no cadastro — confira antes de enviar.</p>
      )}
      <fieldset>
        {ENTITY_KINDS.map((opcao) => (
          <label key={opcao} style={{ display: 'block' }}>
            <input
              type="radio"
              name="entity-kind"
              value={opcao}
              checked={kind === opcao}
              onChange={() => setKind(opcao)}
            />
            {' '}
            {ENTITY_KIND_LABELS[opcao]}
          </label>
        ))}
      </fieldset>
      {erro && <p role="alert">{erro}</p>}
      <button type="submit" disabled={enviando}>
        {enviando ? 'Enviando…' : 'Enviar pedido'}
      </button>
    </form>
  )
}
