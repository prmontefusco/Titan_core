import type { EntityKind } from './api/entityTypeRequests'

export const ENTITY_KIND_LABELS: Record<EntityKind, string> = {
  ADMIN: 'Administrador',
  PRODUTOR: 'Produtor (e funcionários)',
  FRIGORIFICO: 'Frigorífico',
  VETERINARIO: 'Veterinário',
  AUDITOR: 'Auditor',
  CERTIFICADOR: 'Certificador',
  CONSUMIDOR: 'Consumidor',
}
