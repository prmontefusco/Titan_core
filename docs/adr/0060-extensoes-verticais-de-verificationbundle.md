# ADR-0060 - Extensoes verticais de VerificationBundle

**Status:** ACEITA
**Data:** 13 de agosto de 2026
**Decisor:** responsavel pelo produto e arquitetura do Titan

## Contexto

O `VerificationBundleService` do Core interpretava diretamente a secao
`vertical.namespace == "livestock"` de um Dossier para declarar scopes e gaps.
Isso viola a independencia do Core: o mecanismo universal pode montar um
Bundle, mas o significado de coverage sanitaria pertence ao Livestock.

## Decisao

O Core passa a aceitar zero ou mais interpretadores de Dossier por uma porta
generica de Application. Cada interpretador recebe o Dossier completo e devolve
somente scopes e gaps declarativos. O Core nao conhece namespace, payload, regra
ou vocabulario de nenhuma vertical.

O primeiro interpretador sera `LivestockVerificationBundleInterpreter`, na
vertical Livestock, reproduzindo a interpretacao atual sem alterar bytes do
Dossier, hashes, assinatura ou verificacao offline.

Chamadores que desejarem escopo setorial compoem explicitamente o servico com o
interpretador da vertical; bundle generico sem interpretador continua valido,
apenas nao declara significado que o Core nao pode conhecer.

## Consequencias

- O Core permanece reutilizavel para novas verticais.
- Livestock controla a evolucao de seus proprios scopes e limitacoes.
- A extensao nao cria entidade, migration, endpoint, consulta externa ou novo
  contrato de assinatura.
- Interpretadores nao podem alterar conteudo do Dossier ou ocultar gaps passados
  pelo chamador; apenas acrescentam declaracoes deduplicadas.

## Alternativas rejeitadas

- Manter condicionais por namespace no Core: acumula dependencia vertical.
- Criar taxonomia universal de coverage agora: abstracao sem segundo caso concreto.
- Deixar de declarar scopes/gaps Livestock: perde explicabilidade ja entregue.
