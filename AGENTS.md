# AGENTS.md — Dashboard Elisa Lobo (Captação de Leads)

> Contexto completo em **`CLAUDE.md`** (mesma pasta) — leia-o antes de mexer no
> projeto. Este arquivo é um resumo para agentes/ferramentas que seguem a
> convenção `AGENTS.md`.
>
> Este repositório já está configurado para o cliente **Elisa Lobo** — não é
> mais um template genérico. Veja `CLAUDE.md` para os detalhes da arquitetura
> de dados (2 planilhas, 2 sub-funis Quiz/WhatsApp).

## Configuração atual (Elisa Lobo)

1. **`build/build.py`:** `SPREADSHEET_ID_META`/`GID_META` (planilha Meta Ads,
   aba Página 1), `SPREADSHEET_ID_LEADS`/`GID_LEADS` (planilha Leads, aba Leads),
   `CLIENT_NAME="Elisa Lobo"`, `MAIN_PRODUCT_PREFIX="EL | E2-CAP"`,
   `TAX_FACTOR=1.1385`.
2. **Critério de MQL:** `is_mql()` em `build.py` — coluna "Nível" == "Intenso".
3. **Sub-funis:** campanhas com `LEAD` no nome cruzam com a planilha de Leads
   (Quiz); campanhas com `ENGJ` no nome usam `Messaging Conversations Started`
   (WhatsApp, sem MQL). `E1-DIST` fica fora.
4. **`build/template.html`:** título/logo já preenchidos ("Elisa Lobo" /
   "Dashboard Elisa Lobo").
5. **`README.md` / `CLAUDE.md` / `SETUP-CRON.md`:** owner `scale-ag`, repo
   `dashboard-elisa-lobo`, URL do GitHub Pages já preenchidos.
6. **GitHub Pages + Actions:** confirmar `build/` + `.github/workflows/deploy.yml`
   na `main` (ativa `workflow_dispatch`); rodar o workflow uma vez.
7. **cron-job.org:** seguir `SETUP-CRON.md` — token fine-grained novo (Actions:
   read/write, só neste repo), nunca reaproveitar um token exposto em chat.
8. **Insights de Tráfego (opcional):** `build/relatorios.json` e
   `build/relatorios_dados.json` começam vazios (`{}`). Ativar: deixar `briefing.yml`
   gerar os números + criar a **Routine do Claude** (`create_trigger` apontando para
   este repo) que redige `relatorios.json` na `main`. **Não vem pronta** — não foi
   criada nesta configuração inicial.
9. **Testar local** com CSVs de amostra antes de publicar (3 páginas, tema
   claro/escuro, multi-seleção).

## Se for replicar este projeto para outro cliente

Veja o **CHECKLIST DE NOVO CLIENTE** no topo de `CLAUDE.md` e o passo a passo
completo em `GUIA-REPLICACAO.md` — a estrutura de 2 planilhas/2 sub-funis
específica da Elisa Lobo não é genérica; um cliente novo com o layout
"Conversas + Meta Ads + Compradores" do template original exigiria voltar a
essa estrutura em `build.py`.

> **Fora do escopo deste template:** não há Cloudflare Worker nem chamada paga à
> API da Anthropic. A automação de Insights é uma Routine agendada do Claude Code
> (item 10). Qualquer outra camada é desenvolvimento novo.

## Engine (não muda entre clientes)
`build/template.html`, `build/app.js`, `build/estilos.css`,
`.github/workflows/deploy.yml`, `.github/workflows/briefing.yml`,
`build/relatorio_lib.py`, `build/coletar_dados_relatorio.py`,
`build/gerar_relatorios.py`, `build/GUIA-INTERPRETACAO-METRICAS.md`,
`GUIA-REPLICACAO.md` — tabelas, filtros, gráficos, heatmap, tema claro/escuro,
coleta/redação dos Insights. Ver `GUIA-REPLICACAO.md` para os detalhes de
implementação (filtro cruzado, engine de tabela, gráficos Chart.js).

> `template.html` e `app.js` são engine, mas carregam o nome do cliente em pontos
> pontuais (título/logo) — já preenchidos com "Elisa Lobo".

## Específico do cliente (troca a cada replicação)
`build/build.py`, `build/identidade-visual.css` (cores, se aplicável),
`build/relatorios.json` + `build/relatorios_dados.json` (conteúdo — começam vazios),
`build/GUIA-RELATORIOS.md` (contexto do funil), `README.md`, `CLAUDE.md`,
`SETUP-CRON.md`.
