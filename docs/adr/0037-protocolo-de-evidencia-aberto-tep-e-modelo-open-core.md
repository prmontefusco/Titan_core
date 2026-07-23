# ADR-0037: Protocolo de Evidência Aberto (TEP) e Modelo Open-Core

* **Status:** Aceita
* **Data:** 2026-07-22
* **Decisor:** Fundador / Engenheiro Principal
* **Domínio Afetado:** Titan Core (`docs`, `packages/shared_kernel`, `packages/core_integrity`)

---

## 1. Contexto e Problema

Grandes clientes corporativos e atores institucionais temem o *lock-in* comercial ao adotarem plataformas proprietárias de auditoria. Para que o Titan se torne o padrão de mercado de integridade e proveniência de evidências, a especificação do formato de dados e os algoritmos de verificação precisam ser abertos e independentes de fornecedor único.

---

## 2. Alternativas Consideradas

1. **Plataforma 100% Proprietária e Fechada:** Máxima proteção de propriedade intelectual inicial, mas alta resistência de adoção por grandes corporações por medo de lock-in.
2. **Código 100% Aberto (Open Source sem monetização empresarial):** Risco de clonagem por concorrentes sem sustentabilidade financeira para o projeto.
3. **Modelo Open-Core com Protocolo Aberto (Titan Evidence Protocol - TEP):** Publicar a especificação do formato de dados TEP e bibliotecas leves de verificação e assinatura sob licença aberta (MIT/Apache 2.0), enquanto a plataforma enterprise de gestão multi-tenant, infraestrutura RLS e motor adversarial permanecem comerciais.

---

## 3. Decisão

Definir o **Titan Evidence Protocol (TEP)** como um padrão aberto de especificação e verificação de evidências, e adotar o modelo de negócios **Open-Core**.

A especificação esquemática das estruturas canônicas do TEP, bibliotecas de verificação offline e validação de assinaturas serão disponibilizadas publicamente. A plataforma comercial Titan oferece a orquestração enterprise, RLS de segurança, serviços SaaS e módulos verticais especializados (como Titan Livestock).

---

## 4. Consequências

### Positivas
* Elimina a barreira de medo de *lock-in* nos clientes empresariais e auditores internacionais.
* Facilita a adoção do Titan como o "Git da Conformidade e Evidências".
* Permite que integradores terceiros construam conectores TEP abertos para qualquer sistema ERP ou IoT.

### Negativas / Riscos
* Exige manutenção pública da documentação do protocolo TEP e gerenciamento de versões e compatibilidade.
