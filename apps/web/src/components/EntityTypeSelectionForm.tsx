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
      <p className="eyebrow">Primeiro acesso</p>
      <h2>Solicite seu acesso à organização</h2>
      <p>
        Escolha como você atua. Este pedido será encaminhado para a organização piloto
        configurada neste ambiente; você não receberá acesso até que um administrador o aprove.
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
        {enviando ? 'Enviando solicitação…' : 'Solicitar acesso'}
      </button>
    </form>
  )
}
