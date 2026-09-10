import { Link } from 'react-router-dom'
import { PageContext } from './PageContext'

interface AnimalFlowContextProps {
  animalId: string
  organizationId: string
  description: string
}

export function AnimalFlowContext({
  animalId,
  organizationId,
  description,
}: AnimalFlowContextProps) {
  return (
    <div>
      <PageContext
        description={description}
        items={[
          { label: 'Organization', value: organizationId },
          { label: 'Animal', value: animalId },
        ]}
      />
      <p className="flow-return-link">
        <Link to={`/animals/${animalId}`}>Voltar ao detalhe operacional do animal</Link>
      </p>
    </div>
  )
}
