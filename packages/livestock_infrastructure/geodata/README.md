# Titan Geodata adapter

Este pacote contem o adapter HTTP opcional para o `Titan_geodata`, provider
externo substituivel previsto pela ADR-0026.

## Configuracao

A integracao fica desligada por padrao. Para habilitar consultas reais ao
provider, configure as duas variaveis no processo da API:

```powershell
$env:TITAN_GEODATA_URL="http://localhost:8001"
$env:TITAN_GEODATA_API_KEY="<chave-do-titan-geodata>"
```

`TITAN_GEODATA_URL` aponta para a raiz do servico, sem `/api/v1`. O adapter
monta os caminhos versionados internamente.

`TITAN_GEODATA_API_KEY` e segredo operacional. Nao registre valores reais neste
repositorio, em logs, em testes ou em documentos de exemplo.

## Fronteira

O adapter consome fatos espaciais, geometria, cobertura e proveniencia de
versoes. Ele nao decide conformidade, elegibilidade, regularidade ambiental ou
resultado comercial. Essa decisao permanece no Titan Core / Livestock.

Sem uma das variaveis, `apps.api.geodata_dependencies.car_lookup_opcional()`
retorna `None`; as rotas dependentes recusam a operacao com `503` e nomeiam a
configuracao ausente.
