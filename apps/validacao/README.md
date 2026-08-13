# Roteiros de validação executável

Cada arquivo abaixo é um roteiro **executável** contra a API real (Passo/ADR
correspondente entre parênteses), no formato descrito em `AGENTS.md` — "O
roteiro de validação manual é executável": descobre sozinho os identificadores
de que precisa, mostra requisição e resposta lado a lado, e diz por que cada
passo existe. Nenhum deles decide sozinho se o comportamento está correto —
isso continua sendo julgamento de quem valida.

Este índice existe porque nenhum outro documento lista os 28 roteiros. Sem
ele, descobrir que um roteiro existe depende de vasculhar este diretório ou o
histórico de commits — o que esta lista resolve para quem audita o sistema de
fora.

## Antes de rodar qualquer roteiro

1. Suba a stack e aplique as migrations (ver `AGENTS.md` — seção Comandos).
2. Semeie dados de demonstração:
   ```powershell
   $env:TITAN_SEED_CONFIRM = "1"
   python -m uv run --locked python -m apps.seed
   ```
3. Suba a API com a `TITAN_OPERATOR_ORGANIZATION_ID` da semeadura mais
   recente — papéis guardam as permissões que existiam quando foram
   semeados, então um roteiro que valida permissão nova exige semeadura e
   API reiniciadas na mesma rodada.
4. Cada roteiro roda com:
   ```powershell
   python -m uv run --locked python -m apps.validacao.<nome_do_arquivo_sem_.py>
   ```
   A maioria aceita `--pausar` (espera ENTER entre passos, para acompanhar em
   ritmo de leitura). Exceção: `__main__.py` roda com `python -m apps.validacao`
   diretamente — é o roteiro do Passo 13.2, que cresceu para incluir também
   reprodução (13.3) e geometria (17.1/17.2).

Três roteiros (marcados **HTTP real** abaixo) chamam serviços externos de
verdade (IBAMA, FUNAI, PRODES/DETER) e exigem as variáveis de ambiente
correspondentes configuradas na API; sem elas, falham com o motivo do
provedor, não com sintoma genérico.

## Índice por área

### Ciclo de vida e genealogia do animal
| Roteiro | Valida |
|---|---|
| `__main__` (Passo 13.2) | Genealogia (maternidade dupla, paternidade múltipla), reprodução (Passo 13.3, ADR-0040) e geometria de propriedade (Passo 17.1/17.2) |

### Território e conformidade ambiental
| Roteiro | Valida |
|---|---|
| `embargo_ibama` | Embargo ambiental do IBAMA — **HTTP real** |
| `funai` | Leitura territorial de terra indígena FUNAI — **HTTP real** |
| `timelines_territoriais` | Timelines territoriais PRODES e DETER — **HTTP real** |

### Sanidade, medicamentos e estabelecimentos
| Roteiro | Valida |
|---|---|
| `prescricao_veterinaria` | Prescrição veterinária (NR-4) |
| `exigibilidade_sanitaria_minima` | Exigibilidade sanitária mínima (Passo 14.3) |
| `classificacao_sanitaria_medicamento` | Classificação sanitária versionada de medicamento (ADR-0056) |
| `coverage_dimensional` | Importação source-neutral de coverage dimensional (NEXT-01) |
| `importacao_qualificacao_estabelecimento` | Importação de asserções de qualificação de estabelecimento (ADR-0045) |

### Comércio e elegibilidade por mercado
| Roteiro | Valida |
|---|---|
| `perfis_mercado` | Listagem de perfis de mercado |
| `mercados_orientados` | Endpoint orientado a mercado (por animal) |
| `mercados_orientados_lote` | Endpoint orientado a mercado (por lote) |
| `matriz_elegibilidade_mercados` | Matriz de elegibilidade por mercado com regras governadas (ADR-0044) |
| `explicacao_comercial` | Explicação comercial orientada a mercado |
| `simulacao_comercial` | Simulação comercial ponta a ponta até o frigorífico |
| `lote_comercial` | Lote com tratamento heterogêneo até o frigorífico |

### Contraparte externa e continuidade documental
| Roteiro | Valida |
|---|---|
| `contraparte_externa` | Contraparte externa e saída estruturada (ADR-0042) |
| `aquisicao_documental` | Aquisição documental composta (ADR-0042) |
| `artefato_transferencia` | Artefato recebido e lacuna de cobertura (ADR-0042) |
| `fato_importado` | Fato importado com autoria preservada (ADR-0042) |
| `captura_externa_sisbov_simulada` | Leitura e revisão de captura SISBOV simulada (Corte 2B) |

### Transformação industrial (abate)
| Roteiro | Valida |
|---|---|
| `transformacao_industrial` | Fan-out, travessia, balanço, dossiê e fan-in do abate (ADR-0046, Passos 11.2–11.6) |

### Governança, decisão e integração operacional
| Roteiro | Valida |
|---|---|
| `governanca_regras` | Governança auditável de regras (ADR-0043) |
| `entity_type_request` | Pedido de tipo de entidade (EntityTypeRequest) |
| `revisao_humana_decisao` | Revisão humana oficial de decisão (LIV-C06) |
| `liv_c09_integracao_operacional` | Limite assíncrono do outbox/inbox de ERP (LIV-C09) |
| `post_liv_01_operational_summary` | Suporte operacional derivado (POST-LIV-01) |
| `post_liv_02a_neutral_contract` | Contrato outbound neutro de ERP (POST-LIV-02A) |

## Rodar todos de uma vez (roteiro de fumaça)

```powershell
python -m uv run --locked python -m apps.validacao.fumaca
```

Roda os 28 roteiros em sequência (cada um como processo separado, sem
mudar nenhum deles) e devolve um resumo: quantos passaram, quais falharam
e as últimas linhas da saída de cada um que falhou. É uma primeira leitura
de saúde do sistema em minutos — não substitui abrir o roteiro individual
para entender *por que* algo falhou, nem decide se a falha é defeito de
código ou ambiente fora do lugar (provider HTTP real não configurado,
semeadura desatualizada). Continua sendo julgamento de quem valida.

## O que este índice não faz

Não substitui a leitura do roteiro: cada um continua sendo a fonte de
verdade sobre o que exatamente é exercitado, passo a passo.
