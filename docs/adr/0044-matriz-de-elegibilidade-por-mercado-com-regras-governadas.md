# ADR 0044 - Matriz de elegibilidade por mercado com regras governadas

Data: 2026-07-26
Status: Aceita

## Problema

A ADR-0041 definiu que elegibilidade nao e propriedade do animal: e uma relacao
entre um sujeito e uma finalidade de mercado. A ADR-0043 definiu governanca,
versao e adocao auditavel de regras. Falta registrar como as duas decisoes se
encontram no produto.

O caso comercial desejado e comparar destinos lado a lado. Exemplo: o mesmo boi
pode ser elegivel para China e Estados Unidos, mas nao para Uniao Europeia, com
explicacao de qual regra impediu a venda para aquele mercado.

## Decisao

A matriz multi-mercado consumira regras governadas do Core. Cada mercado ou
perfil de destino sera representado na vertical como finalidade operacional, por
exemplo:

- `exportacao-uniao-europeia`
- `exportacao-china`
- `exportacao-estados-unidos`

Cada finalidade usa as versoes de regras adotadas pela Organization. A avaliacao
executa as regras aplicaveis lado a lado e devolve, por mercado, estado,
regras consideradas, motivos, evidencias e lacunas.

Estados iniciais da matriz:

- `ELEGIVEL`
- `NAO_ELEGIVEL`
- `CONDICIONADO`
- `INDETERMINADO`
- `AUSENTE`

## Incrementos

1. A elegibilidade sanitaria atual deve registrar qual adocao e qual versao de
   regra governada sustentaram a decisao, sem trocar o motor inteiro.
2. Em seguida, a vertical Livestock deve expor uma matriz por mercado de destino,
   inicialmente para Uniao Europeia, China e Estados Unidos.
3. Regras iguais entre mercados podem reutilizar a mesma versao adotada; regras
   diferentes ficam isoladas por finalidade.

## Consequencias

- Alterar regra da Uniao Europeia nao afeta decisoes historicas nem mercados que
  nao usam aquela regra.
- Ausencia de regra declarada para um mercado vira `AUSENTE`, nao aprovacao.
- Ausencia de dado exigido vira `INDETERMINADO` ou `NAO_ELEGIVEL` conforme a
  regra adotada, nunca silencio.
- A resposta comercial passa a explicar "onde este ativo pode gerar valor", e
  nao apenas bloquear ou aprovar genericamente.

## Relacionadas

ADR-0041, ADR-0043, ADR-0016, ADR-0026.
