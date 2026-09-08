# Dashboard de Captura de Leads · Elisa Lobo

Dashboard **100% na nuvem** do Funil de Captação de Leads de **Elisa Lobo** que
cruza a planilha de **Leads** (funil Quiz) com o investimento de mídia paga
(**Meta Ads**), calcula os **Leads Qualificados (MQLs)** por anúncio e também
acompanha o sub-funil **WhatsApp** (Conversas Iniciadas, sem MQL). Publicada no
**GitHub Pages**, reconstrói sozinha a cada ~30 min, disparada pelo
**cron-job.org** — sem depender de nenhum PC ligado.

**URL pública:** `https://scale-ag.github.io/dashboard-elisa-lobo/`

---

## O que ela mostra

- **KPIs**: Gasto Total, Leads Totais, CPL, **MQLs** (Nível "Intenso"), CPMQL, Tx-MQL, Impressões, Cliques, CTR, CPC, CPM, e **Conversas Iniciadas** (sub-funil WhatsApp).
- **Evolução diária**: gasto/dia, leads × MQLs/dia, CPL × CPMQL/dia.
- **Qualificação & origem**: leads por área prioritária (MQL destacado), por origem (mídia paga vs. orgânico) e por plataforma.
- **Cruzamento por campanha**: gasto (mídia paga) × leads/MQLs (Quiz) e Conversas Iniciadas (WhatsApp) → CPL, CPMQL, Tx-MQL e Custo/Conversa calculados.
- **Tabela de leads qualificados** (e-mail e telefone **mascarados**, pois a página é pública).
- **Toggle de imposto da mídia paga** (ativo por padrão, fator 1,1385) e **modo claro/escuro**.
- **Aba Relatório**: painel de metas editável + Top/Piores Anúncios + Insights de Tráfego (texto, preenchido manualmente ou por automação própria — ver `build/GUIA-RELATORIOS.md`).

## Critério de Lead Qualificado (MQL)

Coluna "Nível" da planilha **Leads** == "Intenso". Lógica em `build.py` → `is_mql`.

Dois sub-funis dentro do prefixo de campanha `EL | E2-CAP` (diferenciados pelo `Campaign Name`):
- **Quiz** (contém `LEAD`): cruza com a planilha de Leads por `Origem (anúncio)` == `Ad Name`, aplica MQL.
- **WhatsApp** (contém `ENGJ`): não cruza com Leads, não tem MQL — métrica de resultado é `Messaging Conversations Started`.

O funil de distribuição (`E1-DIST`) fica de fora deste dashboard.

## Fontes de dados (somente leitura)

Duas planilhas separadas (não escritas pelo build):

| Planilha | Aba | gid | Uso |
|-----|-----|-----|-----|
| Meta Ads (`12pV1kFQQ0uGgH4JBSY3SgW-2N9R7vnNaptf7u6Et1_I`) | Página 1 | `0` | investimento, impressões, cliques, Messaging Conversations Started |
| Leads (`1Fl4PL3M8J28nDzEuVcZxmOkjyyDnBiHLJStb6VlSsDY`) | Leads | `0` | leads do funil Quiz, Nível de qualificação, Origem (anúncio) |

O build lê essas abas via **export CSV público** (`.../export?format=csv&gid=...`).
**Nada é escrito de volta** nas planilhas. Não há fonte de vendas/faturamento
nesta fase — essas métricas aparecem como "-".

---

## Arquitetura

```
cron-job.org  ──(POST workflow_dispatch a cada 30 min)──▶  GitHub Actions
                                                              │
                          build/build.py  lê os CSVs ◀────────┘
                                 │  cruza dados + calcula MQLs
                                 ▼
                          dist/index.html  ──▶  deploy  ──▶  GitHub Pages (URL pública)
```

- `build/build.py` — baixa os CSVs, cruza os dados, gera `dist/index.html`.
- `build/template.html` — layout/gráficos/tema (Chart.js via CDN).
- `.github/workflows/deploy.yml` — roda o build e publica no Pages.

**Cache-bust:** a página usa `Cache-Control: no-cache`, mostra o horário do último
build, tem botão **Atualizar** e se recarrega sozinha (`?t=timestamp`) ~30 min após
aberta — sempre pegando a versão mais nova.

## Rodar localmente (opcional)

```bash
python build/build.py --out dist/index.html            # busca os CSVs ao vivo
# ou, com arquivos locais para teste:
python build/build.py --meta-file meta.csv --leads-file leads.csv --out dist/index.html
```

---

## Ativação (uma vez) e cron-job.org

O disparo por `workflow_dispatch` só funciona quando o workflow está na branch
**`main`**. Veja **`SETUP-CRON.md`** para o passo a passo e os valores exatos
(URL, headers e body, com marcadores a preencher) a colar no cron-job.org.

> ⚠️ **Segurança:** nunca comite tokens no repositório. Gere um token
> *fine-grained*, só com **Actions: read/write** neste repositório, e use-o
> apenas no cron-job.org (ou em GitHub Secrets, se aplicável).

## Como usar este template para um novo cliente

Veja o **CHECKLIST DE NOVO CLIENTE** no topo de `CLAUDE.md` (ou `AGENTS.md`) e
o passo a passo completo em `GUIA-REPLICACAO.md`.
