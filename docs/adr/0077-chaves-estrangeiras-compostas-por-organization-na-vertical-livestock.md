# ADR-0077 — Chaves estrangeiras compostas por Organization na vertical Livestock

**Data:** 09/09/2026  
**Status:** ACEITA  
**Escopo:** FINDING-003; isolamento relacional entre `rural_properties`, `animals`, `animal_movements`, `property_stays` e `livestock_lots`.

## Contexto

A auditoria adversarial apontou que algumas tabelas da vertical Livestock referenciam `core_audit.rural_properties.property_id` por chave estrangeira simples. Como constraints relacionais não aplicam RLS como autorização de negócio, uma linha de uma Organization poderia apontar para uma propriedade de outra Organization caso conhecesse o UUID.

`rural_properties` já possui a identidade composta `(record_owner_organization_id, property_id)`. O problema está nas FKs consumidoras que não carregam a Organization na própria constraint.

## Decisão

As referências internas da vertical Livestock para `rural_properties` devem usar chaves estrangeiras compostas contendo `record_owner_organization_id` e `property_id`.

O primeiro corte altera:

- `animals.birth_property_id`;
- `animal_movements.origin_property_id`;
- `animal_movements.destination_property_id`;
- `property_stays.property_id`;
- `livestock_lots.property_id`.

O serviço de cadastro de animal também deve validar explicitamente que `birth_property_id` pertence à Organization ativa antes de criar o animal, retornando ausência uniforme no nível de aplicação em vez de depender de erro relacional.

## Consequências

- UUID conhecido de propriedade alheia deixa de satisfazer integridade relacional para linhas de outra Organization.
- Erros de banco deixam de funcionar como oráculo de existência cross-tenant nesse recorte.
- A mudança não altera contrato HTTP, payload público, regra sanitária, ownership histórico ou autorização.
- Referências a animais/lotes ainda podem exigir endurecimentos próprios em cortes posteriores; esta ADR não declara correção universal de todas as FKs simples da plataforma.

## Verificação

Testes devem provar:

- metadata e migration sem drift;
- cadastro de animal recusa propriedade de outra Organization antes de salvar;
- o banco rejeita DML direto tentando referenciar propriedade de outra Organization em animal, movimento, permanência e lote;
- fluxos existentes de animal, movimento e lote continuam funcionando para propriedades da mesma Organization.
