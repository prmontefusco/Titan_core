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

export const ENTITY_KIND_DASHBOARD_DESCRIPTIONS: Record<EntityKind, string> = {
  ADMIN: 'Aprova ou nega pedidos de vínculo à Organization.',
  PRODUTOR: 'Gerencia propriedades, animais e o rebanho da Organization.',
  FRIGORIFICO: 'Recebe lotes e registra transformações industriais.',
  VETERINARIO: 'Registra tratamentos, medicações e atestados sanitários.',
  AUDITOR: 'Consulta o histórico e a elegibilidade sem poder de escrita.',
  CERTIFICADOR: 'Avalia conformidade e emite certificações.',
  CONSUMIDOR: 'Consulta a rastreabilidade e a origem dos produtos.',
}
