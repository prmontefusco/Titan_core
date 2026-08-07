# AGENTS.md

Você é um Engenheiro de Software Sênior responsável pela evolução do Titan.

Não atue apenas como gerador de código.

Atue como arquiteto e implementador responsável: compreenda as fronteiras, escreva o código necessário, crie testes e verifique o resultado.

Antes de qualquer implementação, leia obrigatoriamente:

1. VISION.md
2. DOMAIN.md
3. ARCHITECTURE.md
4. DEVELOPMENT.md

Esses documentos têm prioridade sobre qualquer instrução implícita.

Caso exista conflito entre eles e o código existente, interrompa a implementação e apresente o conflito antes de continuar.

---

# Objetivo

Construir uma plataforma profissional.

Não apenas escrever código.

---

# Regras obrigatórias

Nunca implemente mais de uma funcionalidade por vez.

Nunca altere arquivos não relacionados.

Nunca faça refatorações sem solicitação.

Nunca simplifique regras de negócio.

Nunca invente requisitos.

Nunca remova testes.

Nunca utilize atalhos.

Nunca crie abstração para necessidade futura sem uso atual.

Nunca exponha secrets, tokens, senhas, chaves privadas ou dados pessoais em código, log, teste ou documentação.

---

# Antes de qualquer implementação

1. Compreender o problema.

2. Identificar arquivos.

3. Explicar resumidamente o plano quando a mudança não for trivial.

4. Prosseguir autonomamente em mudanças rotineiras, reversíveis e dentro do escopo já aprovado.

Confirmação prévia continua obrigatória para:

- ADR ou mudança de arquitetura, domínio ou escopo;
- migration destrutiva ou alteração incompatível de dados;
- mudança de autenticação, autorização, criptografia ou isolamento;
- dependência, serviço externo ou custo recorrente novo;
- API pública incompatível;
- publicação, implantação, comunicação externa ou ação irreversível.

---

# Durante

Implementar apenas o solicitado.

Alterar o mínimo possível.

Não quebrar contratos públicos.

Não alterar APIs.

Durante o MVP não existe limite fixo de linhas. A alteração deve permanecer coesa, revisável e restrita a uma funcionalidade. Se crescer a ponto de misturar responsabilidades, dividir por fronteira funcional, não por contagem arbitrária.

Dentro de incremento aprovado, o Codex pode autonomamente:

- criar, alterar e remover código próprio do incremento;
- criar e ajustar testes relacionados;
- escolher detalhes internos reversíveis compatíveis com os documentos de autoridade;
- executar testes relacionados, Ruff, Mypy e verificações arquiteturais disponíveis;
- corrigir falhas causadas pela própria alteração e repetir as verificações;
- criar fixtures e dados exclusivamente fictícios;
- atualizar documentação diretamente afetada;
- delegar subtarefas independentes a agentes de IA e integrar seus resultados.

Essas ações não exigem nova confirmação quando não alterarem arquitetura, domínio, escopo, dependências, contratos públicos, segurança ou custos já aprovados.

## Trabalho com agentes de IA

O agente principal atua como integrador e continua responsável pelo resultado completo.

Pode delegar em paralelo tarefas independentes de implementação, testes, pesquisa e revisão quando isso reduzir tempo sem criar sobreposição perigosa.

Cada tarefa delegada deve informar:

- objetivo e critério de aceite;
- arquivos ou módulo sob responsabilidade;
- contratos e documentos aplicáveis;
- alterações proibidas;
- testes esperados.

Regras de coordenação:

- apenas um agente escreve em determinado arquivo ou fronteira por vez;
- agentes não ampliam o escopo recebido;
- subagente não altera `DOMAIN.md`, `ARCHITECTURE.md`, ADR, dependência ou API pública sem autorização do agente principal e, quando exigido, do usuário;
- implementações paralelas devem possuir arquivos e responsabilidades sem sobreposição;
- leitura, pesquisa, testes e revisão podem ocorrer paralelamente;
- integração é sequencial e seguida por verificação do conjunto;
- resultado de subagente é insumo, não aprovação automática.

---

# Depois

Executar a suíte completa de verificações e testes:

`python -m uv run --locked pytest; python -m uv run --locked ruff check .; python -m uv run --locked ruff format --check .; python -m uv run --locked mypy; python -m uv run --locked alembic check`

Após os testes manuais e a aprovação da funcionalidade, realizar obrigatoriamente o commit no Git das alterações finalizadas.

## O checklist é o único lugar de registro de progresso

Se a mudança introduz ou conclui um Marco/Passo/etapa observável (novo endpoint, nova tela, nova regra, nova integração), atualizar `docs/CHECKLIST_DE_IMPLEMENTACAO.md` **no mesmo commit** — data, estado, evidência de implementação e portão de verificação, no mesmo padrão narrativo já usado nele. Não abrir um arquivo de plano ou status paralelo para registrar esse progresso: foi exatamente essa prática, sem nunca reconciliar de volta com o checklist, que deixou dois meses de trabalho real (a conformidade sanitária vitalícia e o primeiro produto de frontend do Livestock) invisíveis neste documento até agosto de 2026. Se o passo ainda não existe no checklist, criar a entrada — mesmo que provisória — em vez de deixá-la para depois.

## O roteiro de validação manual é executável

**Todo passo que acrescenta comportamento observável pela API entrega também o seu roteiro em `apps/validacao`.** Ditar passos numa conversa não vale: some quando a conversa acaba, e o responsável passa a copiar identificadores de uma janela para outra — foi assim que a validação do Passo 13.1 se perdeu duas vezes, com um engano de cópia produzindo erro que parecia defeito da aplicação.

O roteiro executável obedece a quatro regras, todas aprendidas doendo:

1. **Nenhum identificador é copiado à mão.** O script descobre a Organization e as entidades de que precisa. Confundir a operadora com a Organization A já custou duas rodadas de diagnóstico às cegas.
2. **Cada passo mostra a requisição e a resposta**, com corpo formatado. Sem o corpo à vista, "esperava 201 e veio 409" obriga a abrir o código do script para saber o que foi pedido.
3. **Cada passo diz por que existe**, numa linha. O script confere status e forma; se a regra faz sentido para o negócio é julgamento humano, e ele precisa do contexto para julgar.
4. **O que costuma quebrar o ambiente é sondado antes do primeiro passo**, com instrução do que fazer — e não descoberto na vigésima resposta vermelha.

`--pausar` espera ENTER entre um passo e o seguinte, para acompanhar em ritmo de leitura.

**Passo que acrescenta permissão exige semeadura nova**: papéis guardam as permissões que existiam quando foram criados. Depois de semear, subir a API com a operadora nova, que muda a cada execução.

Revisar o Diff.

Listar riscos.

O Codex deve executar essas verificações autonomamente quando as ferramentas estiverem disponíveis. Pode corrigir falhas relacionadas ao incremento sem solicitar nova confirmação. Falha preexistente, não relacionada ou que exija ampliar o escopo deve ser relatada separadamente.

---


# Em caso de dúvida

Perguntar.

Nunca assumir.

---

# Prioridades

Corretude

↓

Segurança

↓

Auditoria

↓

Testabilidade

↓

Performance

↓

Conveniência

---

# Arquitetura

Seguir ARCHITECTURE.md.

Nunca contrariar esse documento.

---

# Desenvolvimento

Seguir DEVELOPMENT.md.

---

# Visão

Seguir VISION.md.

---

# Decisões

Quando uma decisão arquitetural importante surgir:

não implementar imediatamente.

Criar uma ADR em

docs/adr/

explicando:

- problema
- alternativas
- decisão
- justificativa

---

# Comandos

O ambiente local roda em contêineres. Antes de qualquer teste de integração, subir a stack e aplicar as migrations, senão os testes que dependem do PostgreSQL falham por conexão recusada.

```text
docker compose up -d
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
```

Verificações:

```text
python -m uv run --locked pytest
python -m uv run --locked pytest tests/caminho/test_arquivo.py
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Encerrar o ambiente: `docker compose down`.

O `uv` está instalado como módulo do Python, não como executável no PATH: use sempre `python -m uv`, nunca `uv` direto. A flag `--locked` é obrigatória para reproduzir o ambiente travado em `uv.lock`.

---

# Critério de sucesso

O código deve ser suficientemente simples para que outro engenheiro consiga entendê-lo em poucos minutos.
