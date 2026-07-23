# ADR-0036: Execução Determinística de Políticas Normativas com Wasm Sandbox

* **Status:** Aceita
* **Data:** 2026-07-22
* **Decisor:** Fundador / Engenheiro Principal
* **Domínio Afetado:** Titan Core (`core_domain`, `core_application`, `core_infrastructure`)

---

## 1. Contexto e Problema

Instrumentos normativos, leis e políticas corporativas mudam ao longo do tempo. Quando uma política é alterada, reavaliar decisões tomadas anos atrás utilizando a versão atual da aplicação pode levar a conclusões incorretas ou anacrónicas.

É necessário garantir que uma avaliação realizada no instante $T_0$ possa ser reexecutada no instante $T_n$ exatamente com o mesmo código de regra e lógica em vigor em $T_0$, de forma determinística e segura.

---

## 2. Alternativas Consideradas

1. **Instanciação de código Python em tempo de execução via `eval`/`exec`:** Inseguro e não determinístico entre versões do interpretador Python.
2. **Hardcoding de condicionais por versão no código da aplicação:** Torna o código-fonte da aplicação ingovernável e propício a regressões com o passar dos anos.
3. **Sandbox Determinístico em WebAssembly (Wasm):** Compilar regras e políticas normativas para bytecode Wasm versionado e imutável, executado em um ambiente de sandbox isolado e determinístico.

---

## 3. Decisão

Adotar um **Sandbox de Execução de Políticas Normativas em WebAssembly (Wasm Sandbox)** no Titan Core (`WasmNormativePolicyEvaluator`, `PolicyExecutionSandbox`, `NormativeExecutionReceipt`).

As regras associadas a uma `NormativeBasis` ou `Policy` podem ser compiladas e armazenadas como bytecode Wasm imutável. A reavaliação de um snapshot histórico recupera o bytecode correspondente à versão exata da regra na data do evento, garantindo auditabilidade determinística perpétua ("viagem no tempo regulatória").

---

## 4. Consequências

### Positivas
* Garantia de execução determinística e reproduzível de regras históricas sem anacronismo.
* Isolamento total de segurança (o bytecode Wasm executa sem acesso a I/O, rede ou sistema de arquivos não autorizados).
* Suporte a múltiplas linguagens de origem (Rust, Go, C, TypeScript) para escrita de regras normativas.

### Negativas / Riscos
* Exige infraestrutura de runtime Wasm (ex: `wasmtime` ou `wasmer`) integrada ao ambiente Python/FastAPI.
