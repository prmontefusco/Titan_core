# Vertical Especificativa: Titan ZFM Logistics

**Versão:** 1.0  
**Status:** Proposta de Vertical Futura  
**Domínio:** Logística Fluvial, Cadeia de Custódia e Conformidade Fiscal da Zona Franca de Manaus  

---

## 1. Contexto e Oportunidade de Mercado

O Polo Industrial de Manaus (PIM), localizado na Zona Franca de Manaus (ZFM), abriga mais de 500 indústrias de grande porte (eletroeletrônicos, duas rodas, bens de consumo). 

Devido à geografia da Região Norte, a imensa maioria dos insumos e peças adquiridos no exterior segue um fluxo logístico complexo:
```text
Origem Internacional (Ásia/Europa/EUA)
  ↓ (Navio Marítimo)
Porto de Transbordo (Belém/PA ou Vila do Conde/PA)
  ↓ (Barcaça Fluvial de Cabotagem)
Calha do Rio Amazonas / Rio Negro
  ↓ (Desembarque no Porto de Manaus)
Recinto Alfandegado / EADI
  ↓ (Transporte Terrestre Local)
Fábrica / Linha de Montagem no PIM
```

### Principais Dores Mapeadas
1. **Quebra de Custódia Fluvial e Avarias:** Extravio de cargas, avarias por umidade/impacto e atrasos recorrentes por conta de secas severas na calha do rio.
2. **Impasse Jurídico e de SLA:** Quando o atraso para a linha de montagem de multinacionais (ex: Honda, Samsung), armadores, operadores portuários, transportadores fluviais e seguradoras trocam acusações por falta de proveniência temporal auditável.
3. **Auditoria de Internamento Fiscal (SUFRAMA / SEFAZ-AM):** Para gozar das isenções tributárias da ZFM (IPI, ICMS, PIS/COFINS), a indústria precisa provar o **internamento efetivo da mercadoria** (via Protocolo de Internamento de Mercadoria - PIN). O risco de autuação fiscal por suspeita de "nota fria" ou desvio de carga é altíssimo.

---

## 2. Aplicação da Arquitetura Titan Core

O `Titan Core` provê todos os mecanismos necessários sem exigir alterações no motor universal de proveniência e auditoria.

### 2.1 Mapeamento de Conceitos do Domínio

| Conceito Titan Core | Aplicação na Vertical ZFM Logistics |
| :--- | :--- |
| **`Organization`** | Armador Marítimo, Operador Portuário, Transportador Fluvial, Agente de Carga, SEFAZ-AM, SUFRAMA, Indústria Consumidora (PIM). |
| **`Asset` / `Subject`** | Contêiner, Lote de Insumos (*Batch*), Palete ou Peça Identificada. |
| **`Claim`** | Declaração de embarque, manifesto de carga fluvial, ateste de recepção no porto, despacho de internamento. |
| **`Evidence`** | Dados de sensores IoT (umidade, impacto), coordenadas AIS/GPS da barcaça, lacre eletrônico, fotos com carimbo temporal, declarações aduaneiras (DUIMP/PIN). |
| **`VerificationStatus`** | Estado da integridade física e documental do lote durante a travessia fluvial. |
| **`PhysicalBoundAssertion`** | Regra que detecta desvio de rota não autorizado, quebra de lacre ou incoerência entre o tempo de travessia e a velocidade da barcaça. |
| **`SingleFileVerificationBundle`** | Dossiê digital autônomo offline entregue aos auditores da SUFRAMA ou reguladores de seguros. |

---

## 3. Modelo de Financiamento e Incentivos de P&D (ZFM)

### 3.1 Obrigação Legal de Investimento em P&D
As indústrias de bens de informática e eletroeletrônicos no PIM são obrigadas por lei (Lei de Informática da ZFM) a investir um percentual do seu faturamento bruto em Pesquisa, Desenvolvimento e Inovação na Região Norte.

### 3.2 Requisitos Estruturais para Captação
- **Presença Local:** Para receber recursos diretos de P&D da ZFM ou editar projetos via FAPEAM/SUFRAMA, a startup ou braço de inovação deve possuir CNPJ e operação registrados no estado do Amazonas (Manaus).
- **Parcerias Estratégicas:** Possibilidade de atuação conjunta com Institutos de Ciência e Tecnologia (ICTs) locais (ex: UFAM, UEA, Instituto INDT, FAPEAM).

---

## 4. Estratégia de Faseamento

1. **Fase Atual (MVP):** Manter o foco absoluto na vertical `Titan Livestock` (Pecuária/Exportação de Carne - EUDR), que valida o motor principal.
2. **Fase Posterior (Expansão):** Utilizar o mesmo `Titan Core` para rodar um piloto de `Titan ZFM Logistics` focado no **Dossiê de Internamento Fiscal (SUFRAMA) + Cadeia de Custódia Fluvial**, captando fomento via P&D local.
