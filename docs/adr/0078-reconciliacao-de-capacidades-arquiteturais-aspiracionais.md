# ADR-0078 — Reconciliação de capacidades arquiteturais aspiracionais

**Data:** 09/09/2026  
**Status:** ACEITA  
**Escopo:** FINDING-006; acurácia documental de Wasm Sandbox, ZKP e `SingleFileVerificationBundle`.

## Contexto

A auditoria adversarial apontou divergência entre a documentação arquitetural e o repositório implementado. `ARCHITECTURE.md` e as ADRs 0033, 0034, 0036 e 0050 descrevem ZKP, dossiê HTML/Wasm autônomo e execução normativa em Wasm como capacidades centrais aprovadas, mas o código atual não contém runtime `wasmtime`/`wasmer`, circuitos ZKP, gerador de `SingleFileVerificationBundle` HTML/Wasm ou execução normativa compilada para WebAssembly.

Os documentos de autoridade já distinguem visão de destino e backlog efetivo: `VISION.md` define destino estratégico, `DOMAIN.md` afirma que a visão não é backlog e `ARCHITECTURE.md` declara que conceitos de visão não obrigam implementação integral no estado corrente. Mesmo assim, a seção de stack e as ADRs citadas não deixavam visível para auditores externos que essas capacidades permanecem como direção aprovada, não como garantia operacional do MVP.

## Decisão

O estado operacional atual do MVP deve ser documentado explicitamente:

- regras normativas e políticas executam hoje em processos Python versionados, sob os contratos de aplicação, testes, auditoria e persistência existentes;
- não há sandbox WebAssembly produtivo, dependência `wasmtime`/`wasmer`, ABI Wasm de regras ou persistência de `NormativeExecutionReceipt` baseada em bytecode Wasm;
- não há verificador ZKP produtivo, circuitos zk-SNARK/zk-STARK, geração ou validação de `ZeroKnowledgeProof`;
- não há exportador produtivo de `SingleFileVerificationBundle` HTML/Wasm autocontido.

As ADRs 0033, 0034 e 0036 permanecem aceitas como direção arquitetural futura. Elas não devem ser citadas como capacidade entregue, controle de segurança vigente ou requisito cumprido enquanto não houver implementação, migration, testes, verificação manual quando aplicável e registro no checklist.

A ADR-0050 permanece vigente para o contrato geral de execução determinística e isolada de `Policy` e `Rule`; sua relação com a ADR-0036 passa a ser lida como compatibilidade futura, não como evidência de runtime Wasm operacional.

## Consequências

- Documentação pública e interna passa a refletir a realidade verificável do repositório.
- Auditores, investidores e usuários técnicos deixam de receber alegação implícita de isolamento Wasm, ZKP ou verificação HTML/Wasm já entregue.
- A arquitetura-alvo de longo prazo é preservada sem forçar implementação prematura de criptografia ou runtime especializado.
- Qualquer implementação futura dessas capacidades exigirá incremento próprio, decisão de produto, threat model proporcional, testes, verificações e atualização do checklist.

## Verificação

O incremento que fecha este achado deve provar apenas a reconciliação documental:

- `ARCHITECTURE.md` distingue capacidades implementadas no MVP de direções futuras aprovadas;
- ADRs 0033, 0034, 0036 e 0050 apontam para esta reconciliação;
- nenhuma dependência, API, migration, contrato público, runtime criptográfico ou regra de negócio é adicionada por este ajuste.
