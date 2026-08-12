# POST-LIV-03 — Ingestão controlada do simulador SISBOV

Status: PROPOSTA  
Design status: AGUARDANDO_REVISAO_HUMANA  
Implementation gate: BLOCKED_PENDING_HUMAN_APPROVAL  
Date: 2026-08-12  
Artifact ID: `POST-LIV-03-DP-v1`

## 1. Objetivo

Provar a fronteira de ingestão de dados de identificação, GTA e movimentação de um
**simulador local** compatível em intenção com SISBOV 2.0, sem alegar integração
oficial, autenticidade governamental, autoridade normativa, cobertura completa ou
autorização de mercado.

O simulador é um instrumento para testar a adaptação. Ele não é SISBOV/MAPA, não é
uma Authority e não torna um fato admissível por si só.

## 2. Inventário confirmado

O repositório vizinho `C:\programing\SISBOV_simulator` fornece API REST local em
`http://localhost:3333/integracao`, com autenticação Access Key/Secret Key para JWT.
Os dados, CAR/OESA/NIRF, SIF e credenciais são explicitamente fictícios. O guia do
próprio simulador registra que paths secundários foram reconstruídos e devem ser
confirmados no Swagger oficial antes de qualquer integração real.

O primeiro recorte de leitura pode usar somente:

- `GET /animal/{numero}/getAnimalPorNumero`;
- `GET /gta/{numeroCompleto}/getGTAPorNumeroCompleto`;
- `GET /gta/{numeroComposto}/movimentacao`.

O adapter nunca usa a rota local `_dev/credenciais`; ela é conveniência do simulador,
não parte do contrato SISBOV.

## 3. Estado reutilizável e lacuna concreta

O Titan já possui:

- identificador `OFFICIAL_SISBOV` no Animal, sem fusão automática de sujeitos;
- `CoverageContribution` source-neutral, com referência opcional, validação e
  admissibilidade explícitas;
- Facts, Evidence, proveniência e avaliação de Policy separados;
- `ReceivedTransferArtifact` para a travessia de custódia da ADR-0042.

Mas `ImportedLivestockFact` e seu serviço atual exigem, materialmente,
`received_transfer_artifact`. Essa restrição está correta para transferência de
custódia e impede que um registro de API externa seja disfarçado como dossiê recebido.

Consequentemente, o adapter SISBOV não pode gravar no fluxo atual de fatos importados
sem antes haver uma decisão explícita sobre um artefato de captura externo
source-neutral. Reusar artificialmente `ReceivedTransferArtifact` é rejeitado.

## 4. Decisão proposta

Separar três responsabilidades:

```text
Simulador local (material externo fictício)
        ↓ captura com request/response, data e digest
External source capture / source artifact
        ↓ parsing e validação estrutural
Imported material assessment
        ↓ (somente após revisão explícita)
Facts + coverage contributions + admissibility para Policy
```

O primeiro adapter será `SISBOV_SIMULATOR_LOCAL`. Toda saída deve carregar a
classificação `SIMULATED` e a identidade da captura. Não haverá fallback para fonte
oficial, nem inferência de autoridade a partir do nome “SISBOV”.

Correspondência de Animal é uma etapa explícita: um número SISBOV coincidente é
evidência de associação, nunca autorização para fundir sujeitos ou importar história
automaticamente. Ausência, colisão ou divergência de identificador interrompem a
operação em estado revisável.

## 5. Semântica do material capturado

| Material | Pode declarar | Não pode declarar automaticamente |
|---|---|---|
| Animal | identificadores e campos retornados | identidade Titan confirmada, origem oficial |
| GTA | número, datas, origem/destino declarados, status retornado | transferência de custódia Titan, conclusão de trajetória |
| Movimentação | vínculo declarado com GTA/animais e status retornado | movimentação ocorrida/finalizada sem regra de validação |
| Resposta vazia/erro | lacuna, inacessibilidade ou falha técnica | inexistência do animal, GTA ou evento |

Coverage só poderá ser gravada por declaração dimensional explícita e revisada. Uma
resposta de API, ainda que completa para sua consulta, não significa cobertura completa
de `identity` ou `movement` em intervalo algum.

## 6. Cortes propostos

### Corte 1 — Captura e parsing puros

Introduzir contratos transitórios de Application para request/capture/resultado do
simulador, um port de transporte e parser estrito para Animal, GTA e Movimentação.
Testes usam transporte falso; não haverá HTTP real, persistência, API Titan,
credenciais, Fact, Evidence, coverage, Policy, Decision ou migration.

Critérios:

1. cada captura preserva source code, endpoint, instante, digest do corpo e marca
   `SIMULATED`;
2. resposta malformada, 401/403/404, timeout e associação ambígua permanecem
   diagnósticos explícitos;
3. o parser não cria `ReceivedTransferArtifact`, `ImportedLivestockFact`, Fact ou
   contribuição de coverage;
4. identificador externo não altera o Animal Titan.

### Corte 2 — Artefato de captura e revisão de associação

Somente após ADR aprovada para o artefato source-neutral: persistir a captura com RLS
e expor o fluxo humano de associação com o Animal local. O roteiro em
`apps/validacao` usará exclusivamente dados fictícios e descobrirá seus IDs, sem cópia
manual. Ainda não haverá importação automática de Facts nem coverage.

### Corte 3 — Material importado controlado

Mapear campos aprovados para Facts importados e/ou contribuições dimensionais usando o
novo artefato. Para cada campo, a Policy precisa decidir admissibilidade. GTA e
movimentação não viram continuidade entre Organizations sem o protocolo da ADR-0042.

## 7. Fora de escopo

- integração oficial SISBOV/MAPA, homologação, produção, white-list, credenciais reais
  ou consulta de documentos oficiais;
- afirmação de reconhecimento externo, certificação ou autorização de exportação;
- emissão, alteração ou cancelamento de GTA e movimentação;
- sincronização em lote, webhook, worker, outbox ou reavaliação;
- cobertura implícita, fusão de animais ou transferência de custódia implícita;
- mudança de Policy, Rule, Authority ou Market Eligibility.

## 8. Riscos e portões

Antes do Corte 2, abrir ADR específica para resolver a lacuna entre `ImportedLivestockFact`
e um artefato externo que não é transferência de custódia. A ADR deve escolher se o
artefato é extensão do modelo de fonte existente ou conceito novo, sem diminuir os
invariantes da ADR-0042.

Antes de qualquer integração oficial, é obrigatório confirmar os contratos no Swagger
liberado pelo MAPA, obter autorização/credenciais/white-list próprias e reclassificar a
fonte conforme evidência efetiva. Nenhuma dessas condições é presumida pelo simulador.

## 9. Próximo passo recomendado

Revisar este package e, se aprovado, implementar **somente o Corte 1**. A implantação
de transporte HTTP contra o servidor local fica deliberadamente posterior: primeiro o
contrato precisa provar que captura simulada não vira autoridade, fato ou coverage por
acidente.
