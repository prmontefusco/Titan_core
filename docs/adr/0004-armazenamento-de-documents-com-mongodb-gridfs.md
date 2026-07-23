# ADR 0004 — Armazenamento de Documents com Object Storage (Google Cloud Storage / MinIO)

* **Status:** Substituída / Atualizada  
* **Data da Atualização:** 22 de julho de 2026 (Substitui decisão original de GridFS)  
* **Decisores:** responsável pelo produto e arquitetura do Titan

---

## 1. Contexto e Problema

Evidence e Dossier referenciam PDFs, imagens, vídeos, certificados e outros Artifacts binários. 
A decisão original de adotar MongoDB/GridFS exigiria que um fundador solo gerenciasse um cluster MongoDB completo de banco noSQL em paralelo ao PostgreSQL, gerando alto fardo operacional de DevOps, sem oferecer suporte nativo a políticas legais de imutabilidade de retenção (*Bucket Lock / WORM*).

---

## 2. Decisão

Substituir o MongoDB GridFS por **Object Storage Padrão (API compatível com S3/GCS)** como camada de armazenamento de arquivos binários do Titan Core:

* **Em Produção (Google Cloud Platform - GCP):** Uso do **Google Cloud Storage (GCS)** com recurso de **Bucket Lock / Retention Policy (WORM - Write Once, Read Many)** ativado. Isso atende às exigências regulatórias de auditoria garantindo que binários salvos não possam ser alterados nem excluídos antes do prazo legal expirado, mesmo por administradores.
* **Em Desenvolvimento Local:** Uso do **MinIO** (ou sistema de arquivos local com interface de Object Storage) via `compose.yaml`, mantendo o custo de desenvolvimento local 100% gratuito.
* **PostgreSQL Permanece a Única Fonte de Verdade:** Todos os metadados de domínio (identity, ownership, SHA-256 calculados pelo Titan, autorização, RLS, status do upload) residem exclusivamente no PostgreSQL.

---

## 3. Consequências

### Positivas
* **Eliminação do MongoDB/GridFS:** Reduz drasticamente a complexidade operacional para fundador solo (uma dependência a menos para manter e auditar em produção).
* **Imutabilidade Legal Nativa (WORM):** O Bucket Lock do GCS oferece prova jurídica indiscutível de que arquivos de evidência não foram alterados ou expurgados indevidamente.
* **Escalabilidade Infinito e Custo Baixo:** O GCS e Cloud Run oferecem plano gratuito (Free Tier) e custo de frações de centavos de dólar por GB.
* **Zero Refatoração entre Local e Nuvem:** O adapter no `core_infrastructure` utiliza a biblioteca padrão de Object Storage (S3/GCS API), mudando apenas variáveis de ambiente entre dev local e GCP.

### Negativas / Riscos
* Dependência de credencial de serviço para acesso ao bucket em produção (gerenciada via IAM de menor privilégio no GCP).
