# ADR-0034: Dossiê Autônomo Monolítico em HTML/Wasm

* **Status:** Aceita
* **Data:** 2026-07-22
* **Decisor:** Fundador / Engenheiro Principal
* **Domínio Afetado:** Titan Core (`core_domain`, `core_integrity`, `core_infrastructure`)

---

## 1. Contexto e Problema

Exportação de relatórios de auditoria em formatos tradicionais (PDF, CSV, JSON simples) gera dependência permanente de infraestrutura online ou de softwares específicos para validar assinaturas e hashes. Se a plataforma emissora ficar indisponível ou for encerrada, a verificabilidade dos relatórios passados fica comprometida.

Além disso, relatórios em PDF podem ser manipulados sem que o leitor humano perceba, enquanto arquivos JSON puros são ilegíveis para auditores não técnicos.

---

## 2. Alternativas Consideradas

1. **PDF com Assinatura Digital PAdES:** Amplamente aceito, mas visualização interativa do grafo de proveniência e recálculo dinâmico de árvores de hash offline são limitados.
2. **Pacote ZIP contendo JSON e CLI de Verificação:** Exige que o auditor instale ferramentas de linha de comando no seu computador, o que gera grande fricção de uso.
3. **Dossiê HTML Monolítico com Kernel de Verificação WebAssembly (Wasm):** Um único arquivo `.html` contendo os dados do dossiê, a árvore de hashes, as chaves públicas e um motor de verificação criptográfica compilado em WebAssembly.

---

## 3. Decisão

Adotar o formato **`SingleFileVerificationBundle`** como um artefato exportável autônomo do Titan Core.

O dossiê é empacotado como um arquivo HTML estático autocontido que carrega internamente um kernel de verificação em WebAssembly. Ao ser aberto em qualquer navegador web (sem conexão à internet), o arquivo executa localmente o recálculo de hashes, validação de assinaturas e renderização gráfica e interativa da proveniência e das lacunas declaradas.

---

## 4. Consequências

### Positivas
* Verificabilidade perpetuada e independente de servidores ou APIs ativas.
* Zero fricção para o auditor (basta dar um duplo clique no arquivo em qualquer computador ou tablet).
* Impossibilidade de falsificação sem que o kernel de verificação acuse alteração no arquivo.

### Negativas / Riscos
* Tamanho do arquivo exportado é maior do que um JSON simples devido ao embutimento do bytecode WebAssembly e da interface interativa.
