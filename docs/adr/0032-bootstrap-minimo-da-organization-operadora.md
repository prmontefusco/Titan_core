# ADR 0032 — Bootstrap mínimo da Organization operadora

**Status:** Aceita
**Data:** 21 de julho de 2026
**Decisores:** fundador e responsável pela arquitetura do Titan

## Contexto e problema

O Titan falha fechado quando faltam vínculos, Roles, Permissions ou perfis. A primeira
inicialização, contudo, precisa materializar a Organization operadora que possui Users,
identidades externas e o catálogo canônico de Permissions. Um seed amplo criaria privilégios
sem caso de uso aprovado e enfraqueceria essa segurança.

## Alternativas

- criar usuário, Membership, Roles e Permissions administrativas universais;
- depender de alteração manual e não auditada no banco;
- criar somente a Organization operadora por comando administrativo explícito e auditável.

## Decisão

O bootstrap inicial cria exclusivamente a Organization operadora, com Identifier fornecido por
configuração administrativa. Não cria User, ExternalIdentity, Membership, Role, Permission,
AuthorizationGrant ou Policy.

A aplicação do perfil `ORGANIZATION_OPERADORA_MINIMA`, versão `1`, registra recibo imutável com
Organization, ambiente, origem, autoridade, versão, instante e resultado. A combinação de perfil,
versão e ambiente é única. Nova execução verifica o recibo existente e retorna `JA_APLICADO` sem
duplicar dados. Configuração divergente falha fechada.

O comando utiliza a conexão administrativa configurada para migrations e bootstrap. Credenciais
de runtime não recebem autoridade implícita para executar o procedimento.

## Invariantes

- bootstrap não concede acesso nem cria permissão universal;
- Identifiers e autoridade são explícitos, nunca gerados silenciosamente pelo comando;
- ambiente pertence a vocabulário controlado em português;
- recibo aplicado não é atualizado nem removido pela aplicação;
- idempotência não permite substituir a Organization de um ambiente;
- ausência de qualquer perfil posterior continua produzindo negação;
- códigos presentes somente em testes não integram o catálogo real.

## Consequências

O primeiro estado confiável torna-se reproduzível e auditável. O provisionamento de atores e
autorizações continuará em casos de uso próprios. A credencial administrativa precisa ser
protegida e executada fora do tráfego normal da API.

## Critérios de aceitação

- ambiente vazio não possuir Organization operadora;
- comando exigir banco, Organization, autoridade e ambiente explícitos;
- primeira execução criar uma Organization e um recibo;
- segunda execução não duplicar nenhum registro;
- configuração divergente ser recusada;
- nenhuma Permission, Role, Membership ou identidade ser criada;
- migration ser reversível e recibo permanecer protegido por RLS.
