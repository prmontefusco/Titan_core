# Roteiro humano — VERIFY/ACCEPT do Dossiê `INTERNAL_ONLY`

Este roteiro executa a SPEC correspondente. Não é roteiro de API e não cria
comportamento novo: a preparação técnica usa somente o Dossier, o
VerificationBundle e o verificador já existentes.

## Preparação da sessão

Um facilitador técnico prepara quatro pacotes sintéticos do perfil `MARKET_TEST_A`:

| Pacote | Condição mínima |
|---|---|
| A | requisito atendido e coverage completa |
| B | evidência/fato necessário ausente, produzindo pendência ou indeterminação |
| C | requisito comprovadamente não atendido |
| D | coverage histórica parcial que impede conclusão positiva |

Para cada pacote, entregar ao leitor somente:

1. `dossier.json` canônico;
2. o `VerificationBundle` exportado;
3. relatório legível do `BundleVerifier` indicando o resultado da verificação.

Não entregar código, ADRs, nomes de testes, banco, logs ou explicação prévia da
arquitetura. Identificar os pacotes apenas como A, B, C e D. Registrar as respostas
do leitor antes de qualquer esclarecimento técnico.

## Perguntas por pacote

Pedir que o leitor localize e responda, citando a parte do artefato que usou:

1. Quem ou qual sujeito está sendo avaliado?
2. Para qual finalidade e perfil?
3. Quando a avaliação ocorreu? Qual é o corte de conhecimento, se informado?
4. Qual foi o resultado da Decision?
5. Por quais razões o resultado foi obtido?
6. Quais requisitos/regras foram avaliados e quais versões foram usadas?
7. Quais requisitos estão satisfeitos, falhos, pendentes ou indeterminados?
8. Que fatos/evidências sustentam a conclusão?
9. Que evidências ou informações estão ausentes?
10. Qual cobertura histórica existe, em qual período e em quais dimensões?
11. Quais limitações impedem ou reduzem a conclusão?
12. Quem emitiu a decisão? Houve revisão humana? Se não houver, o que o artefato
    permite afirmar honestamente?
13. A conclusão possui certificação, autorização de exportação ou reconhecimento
    externo? Onde isso é demonstrado ou negado?
14. O que a verificação do Bundle confirma? O que ela não confirma?

## Checagens específicas dos cenários

### A — Elegível internamente

O leitor deve identificar conclusão interna favorável, requisitos satisfeitos,
coverage completa e a frase/limite que nega reconhecimento externo. Deve distinguir
“integridade válida” de “autorização para exportar”.

### B — Evidência ausente

O leitor deve apontar qual informação falta e concluir que o Titan não conseguiu
provar o requisito. Não deve interpretar ausência como reprovação definitiva nem
como aprovação.

### C — Requisito violado

O leitor deve identificar regra violada, fato que a sustenta, razão da Decision e
ação corretiva, quando declarada. Não deve chamar a conclusão interna de sanção ou
determinação de autoridade externa.

### D — Coverage histórico parcial

O leitor deve separar informação válida disponível de cobertura insuficiente e
explicar por que a lacuna impede conclusão positiva. Não deve confundir coverage
parcial com prova de irregularidade.

## Classificação de achados

Para cada resposta incorreta, ambígua ou dependente de explicação técnica, registrar:

| Classe | Usar quando |
|---|---|
| DATA | a informação necessária não está no artefato nem nas capacidades existentes |
| DOMAIN | o conceito necessário não é representável corretamente pelo domínio |
| PRESENTATION | a informação existe, mas sua forma impede compreensão prática |
| TERMINOLOGY | o vocabulário técnico impede compreensão adequada |
| TRACEABILITY | origem, razão, ligação entre fato e conclusão ou período não está clara |
| PRODUCT | a informação apresentada não corresponde à necessidade do leitor |
| NONE | comportamento satisfatório |

Somente `DATA` ou `DOMAIN` justificam reconsideração estrutural imediata.
`PRESENTATION`, `TERMINOLOGY`, `TRACEABILITY` e `PRODUCT` geram hipótese para
Discovery posterior, não requisito automático.

## Registro de resultado

Ao final, registrar para cada pacote:

- respostas do leitor;
- localização indicada no artefato;
- classificação de cada achado;
- se houve necessidade de explicação técnica;
- resultado parcial: `ACCEPTED`, `ACCEPTED_WITH_GAPS` ou `REJECTED`.

Resultado global:

- **ACCEPTED:** nenhum ponto crítico exige ajuda técnica e não há interpretação
  indevida de reconhecimento externo;
- **ACCEPTED_WITH_GAPS:** o leitor compreende a decisão, mas há problemas não
  estruturais de apresentação, linguagem, produto ou rastreabilidade;
- **REJECTED:** o artefato não permite responder a uma pergunta essencial, induz
  conclusão errada ou depende de conhecimento interno do Titan.

## Preparação para Discovery externa, somente após aceite interno

Se o resultado global for `ACCEPTED` ou `ACCEPTED_WITH_GAPS`, usar o artefato como
instrumento de Discovery — não como material comercial — e perguntar a um
frigorífico/comprador:

1. Esse problema existe? Como a aptidão de animal/lote é avaliada hoje?
2. Quem faz a análise, quem revisa e quem pode agir sobre a conclusão?
3. Quais informações importam, faltam ou são dispensáveis?
4. Onde há retrabalho, espera, erro ou impacto econômico?
5. O artefato ajudaria a entender ou conferir uma decisão? Por quê?
6. Quem seria usuário, patrocinador, autoridade de confiança e potencial pagador?

Não apresentar o resultado como certificação, autorização, integração oficial ou
conformidade regulatória.
