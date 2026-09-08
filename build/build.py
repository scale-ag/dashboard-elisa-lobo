#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera a dashboard estatica (index.html) a partir de 2 planilhas do Google Sheets
da Elisa Lobo (Captacao de Leads):

  - Meta Ads (planilha "Meta Ads", aba "Pagina 1", gid GID_META): investimento,
    impressoes, cliques e "Messaging Conversations Started" por dia/campanha/
    conjunto/anuncio.
  - Leads (planilha "Leads", aba "Leads", gid GID_LEADS): leads do funil Quiz,
    com nota/nivel de qualificacao e o anuncio de origem.

Dentro do prefixo de campanha MAIN_PRODUCT_PREFIX ("EL | E2-CAP") existem DOIS
sub-funis, diferenciados pelo Campaign Name:
  - contem "LEAD"  -> funil Quiz: cruza com a planilha de Leads (por Origem
    (anuncio) == Ad Name) e aplica o criterio de MQL.
  - contem "ENGJ"  -> funil WhatsApp: NAO cruza com Leads (nao tem MQL) — a
    metrica de resultado e "Messaging Conversations Started" (campo "cv" nos
    registros de meta[]).
Campanhas fora do prefixo (ex. E1-DIST) ficam de fora do dashboard.

Criterio de Lead Qualificado (MQL): coluna "Nivel" da planilha Leads == "Intenso".

Este script apenas LE as planilhas (export CSV publico) e emite os REGISTROS
BRUTOS (leads[] e meta[]) dentro do HTML. Nao ha fonte de vendas/faturamento
nesta fase — sales[] fica sempre vazio (Vendas/CAC/ROAS aparecem "-"). Todos
os filtros, agregacoes, KPIs, tabelas e graficos sao calculados no navegador
(client-side). Nunca escreve nada de volta nas planilhas.

Teste local: --meta-file / --leads-file apontando para CSVs baixados.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
import unicodedata
import urllib.request
from datetime import datetime, timezone, timedelta

# Planilha Meta Ads (aba "Pagina 1")
SPREADSHEET_ID_META = "12pV1kFQQ0uGgH4JBSY3SgW-2N9R7vnNaptf7u6Et1_I"
GID_META = "0"
# Planilha Leads (aba "Leads")
SPREADSHEET_ID_LEADS = "1Fl4PL3M8J28nDzEuVcZxmOkjyyDnBiHLJStb6VlSsDY"
GID_LEADS = "0"
EXPORT_URL = "https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid={gid}"

# Identificação do cliente/conta (usada só em textos/relatórios — não afeta o cruzamento de dados).
CLIENT_NAME = "Elisa Lobo"
MAIN_PRODUCT = "Captação de Leads"
# Prefixo comum às campanhas do funil coberto por este dashboard. O funil de
# distribuição (E1-DIST) não usa este prefixo e fica de fora automaticamente.
MAIN_PRODUCT_PREFIX = "EL | E2-CAP"
# Siglas que diferenciam os dois sub-funis dentro do prefixo acima.
SUBFUNNEL_QUIZ_TAG = "LEAD"       # cruza com a planilha de Leads, aplica MQL
SUBFUNNEL_WHATSAPP_TAG = "ENGJ"   # não cruza com Leads; métrica = Messaging Conversations Started

BRT = timezone(timedelta(hours=-3))   # horario de Brasilia (exibicao)
TAX_FACTOR = 1.1385   # imposto/taxa da conta de mídia (13,85%)

# --------------------------------------------------------------------------- #
# Regras da aba Relatório (Top/Piores anúncios)
# --------------------------------------------------------------------------- #
# Amostra mínima para julgar um anúncio como "vencedor" ou "ruim". Abaixo disso
# ele entra como "Em observação" (dado insuficiente) — nunca é classificado só
# porque teve 1 resultado com pouco investimento. Ajuste conforme o ticket/CAC.
SAMPLE_MIN_SPEND = 100.0   # gasto mínimo (R$) para amostra relevante
SAMPLE_MIN_MQLS = 3        # MQLs mínimos para julgar qualidade profunda
TOP_ADS_N = 10             # nº de linhas em Top / Piores anúncios

# Metas & parâmetros da conta (DEFAULTS do painel editável da aba Relatório).
# São só o valor inicial: o usuário edita no navegador (persistido em
# localStorage) e as tabelas de anúncios recoram CPMQL/CAC e reavaliam a
# amostra ao vivo. None = "meta não definida" (métrica aparece sem cor até o
# gestor preencher).
META_CPMQL = None          # meta de CPMQL (R$/MQL); None = não definida
META_CAC = None            # meta de CAC (R$/venda); None = não definida
VOLUME_MIN_AMOSTRAL = SAMPLE_MIN_MQLS  # conversões (MQLs) mínimas p/ amostra confiável
N_DIAS_CORTE = 5           # dias consecutivos acima do teto p/ considerar corte


# --------------------------------------------------------------------------- #
# Leitura
# --------------------------------------------------------------------------- #
def fetch_csv(url: str) -> list[list[str]]:
    req = urllib.request.Request(url, headers={"User-Agent": "dash-template-bot/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return list(csv.reader(io.StringIO(raw)))


def read_csv_file(path: str) -> list[list[str]]:
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        return list(csv.reader(f))


def load_rows(url: str, local: str | None) -> list[list[str]]:
    return read_csv_file(local) if local else fetch_csv(url)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm(s: str | None) -> str:
    return strip_accents((s or "").strip().lower())


def to_float(v) -> float:
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d,.\-]", "", str(v).strip())
    if not s:
        return 0.0
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_date(v: str) -> str | None:
    if not v:
        return None
    s = str(v).strip()
    if not s:
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    s = s.replace("\xa0", " ").replace(",", " ")
    s = re.sub(r"\s+", " ", s).strip()
    for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%d/%m/%y", "%b %d %Y", "%Y/%m/%d",
                "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M",
                "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M",
                "%d/%m/%Y %I:%M:%S %p", "%m/%d/%Y %I:%M:%S %p",
                "%d/%m/%Y %I:%M %p", "%m/%d/%Y %I:%M %p"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    # último recurso: pega só o "pedaço" de data antes do 1º espaço (data + hora
    # num formato não previsto acima) e tenta de novo só a parte da data.
    if " " in s:
        return parse_date(s.split(" ", 1)[0])
    return None


def is_test_lead(rowtext: str) -> bool:
    return "<test lead" in rowtext.lower()


def is_mql(v: str | None) -> bool:
    """Critério de MQL: coluna "Nível" da planilha Leads == "Intenso"."""
    return norm(v) == "intenso"


def pretty_area(v: str) -> str:
    s = (v or "").strip()
    return s if s else "Sem resposta"


def mask_email(e: str) -> str:
    e = (e or "").strip()
    if "@" not in e:
        return "—"
    user, dom = e.split("@", 1)
    keep = user[:2] if len(user) > 2 else user[:1]
    return f"{keep}****@{dom}"


def mask_phone(p: str) -> str:
    digits = re.sub(r"\D", "", p or "")
    return f"…{digits[-4:]}" if len(digits) >= 4 else "—"


def first_last_initial(name: str) -> str:
    parts = (name or "").strip().split()
    if not parts:
        return "—"
    return parts[0] if len(parts) == 1 else f"{parts[0]} {parts[-1][:1]}."


# --------------------------------------------------------------------------- #
# Indexacao das colunas
# --------------------------------------------------------------------------- #
def header_index(header, wanted, fallback=None):
    fallback = fallback or {}
    idx = {}
    hn = [norm(h) for h in header]
    for key, aliases in wanted.items():
        found = None
        for a in aliases:
            a = norm(a)
            for i, h in enumerate(hn):
                if h == a or (a and a in h):
                    found = i
                    break
            if found is not None:
                break
        idx[key] = found if found is not None else fallback.get(key)
    return idx


def cell(row, i):
    if i is None or i < 0 or i >= len(row):
        return ""
    return (row[i] or "").strip()


def subfunnel_of(campaign_name: str) -> str | None:
    """Classifica a campanha em 'quiz' (LEAD) ou 'whatsapp' (ENGJ), ou None se
    não pertencer ao prefixo do dashboard (MAIN_PRODUCT_PREFIX) ou não bater
    com nenhuma das duas siglas conhecidas."""
    if MAIN_PRODUCT_PREFIX not in campaign_name:
        return None
    if SUBFUNNEL_QUIZ_TAG in campaign_name:
        return "quiz"
    if SUBFUNNEL_WHATSAPP_TAG in campaign_name:
        return "whatsapp"
    return None


# --------------------------------------------------------------------------- #
# Processamento -> registros brutos
# --------------------------------------------------------------------------- #
def process(meta_rows, leads_rows):
    mheader = meta_rows[0] if meta_rows else []
    midx = header_index(mheader, {
        "day": ["day", "data"],
        "campaign": ["campaign name", "campaign"],
        "adset": ["ad set name", "adset"],
        "ad": ["ad name"],
        "spent": ["amount spent", "valor gasto", "gasto"],
        "impr": ["impressions", "impress"],
        "clicks": ["link clicks", "clicks", "cliques"],
        "pv": ["landing page views", "page views"],
        "conv": ["messaging conversations started"],
    })
    has_pv = midx["pv"] is not None
    has_chk = False  # sem coluna de Adds to Cart/Checkout nesta conta

    meta = []
    ad_camp_adset: dict[str, dict] = {}   # Ad Name -> {"camp":..,"adset":..} (1ª ocorrência)
    unknown_campaigns: set[str] = set()
    for row in meta_rows[1:]:
        if not any((c or "").strip() for c in row):
            continue
        campaign = cell(row, midx["campaign"])
        sub = subfunnel_of(campaign)
        if sub is None:
            if campaign and MAIN_PRODUCT_PREFIX in campaign:
                unknown_campaigns.add(campaign)
            continue
        ad = cell(row, midx["ad"]) or "(sem anúncio)"
        adset = cell(row, midx["adset"]) or "(sem conjunto)"
        ad_camp_adset.setdefault(norm(ad), {"camp": campaign, "adset": adset, "ad": ad})
        meta.append({
            "d": parse_date(cell(row, midx["day"])),
            "camp": campaign or "(sem campanha)",
            "adset": adset,
            "ad": ad,
            "sub": sub,
            "sp": round(to_float(cell(row, midx["spent"])), 4),
            "im": to_float(cell(row, midx["impr"])),
            "cl": to_float(cell(row, midx["clicks"])),
            "pv": to_float(cell(row, midx["pv"])) if has_pv else 0.0,
            "ck": 0.0,
            # Messaging Conversations Started só existe (é > 0) nas campanhas
            # ENGJ (WhatsApp); nas LEAD (Quiz) a coluna vem vazia/zero.
            "cv": to_float(cell(row, midx["conv"])),
        })
    if unknown_campaigns:
        print(f"  AVISO: {len(unknown_campaigns)} campanha(s) dentro do prefixo "
              f"'{MAIN_PRODUCT_PREFIX}' sem sigla LEAD/ENGJ reconhecida (ignoradas):",
              file=sys.stderr)
        for c in sorted(unknown_campaigns):
            print(f"    - {c}", file=sys.stderr)

    lheader = leads_rows[0] if leads_rows else []
    lidx = header_index(lheader, {
        "created": ["data/hora", "data"],
        "name": ["nome"],
        "email": ["e-mail", "email"],
        "phone": ["telefone"],
        "nivel": ["nivel"],
        "area": ["area prioritaria", "área prioritária"],
        "origem": ["origem (anuncio)", "origem"],
    })

    leads = []
    unmatched = 0
    unmatched_samples: list[str] = []
    bad_date_samples: list[str] = []
    total_rows = 0
    for row in leads_rows[1:]:
        if not any((c or "").strip() for c in row):
            continue
        if is_test_lead(" ".join(str(c) for c in row)):
            continue
        total_rows += 1
        origem = cell(row, lidx["origem"])
        match = ad_camp_adset.get(norm(origem)) if origem else None
        if match:
            src, camp, adset, ad = "meta", match["camp"], match["adset"], match["ad"]
        else:
            if origem:
                unmatched += 1
                if len(unmatched_samples) < 8:
                    unmatched_samples.append(origem)
            src, camp, adset, ad = "org", "(sem campanha)", "(sem conjunto)", (origem or "(sem anúncio)")
        area = pretty_area(cell(row, lidx["area"]))
        raw_date = cell(row, lidx["created"])
        parsed_date = parse_date(raw_date)
        if raw_date and not parsed_date and len(bad_date_samples) < 8:
            bad_date_samples.append(raw_date)
        leads.append({
            "d": parsed_date,
            "src": src,
            "plat": "ig" if src == "meta" else "—",
            "camp": camp,
            "adset": adset,
            "ad": ad,
            "prof": area,
            "bucket": area,
            "q": 1 if is_mql(cell(row, lidx["nivel"])) else 0,
            "utm": 1 if src == "meta" else 0,
            "nm": first_last_initial(cell(row, lidx["name"])),
            "em": mask_email(cell(row, lidx["email"])),
            "ph": mask_phone(cell(row, lidx["phone"])),
        })
    print(f"  [diagnóstico] linhas de lead válidas na planilha Leads: {total_rows}  "
          f"({sum(1 for l in leads if l['d'])} com data reconhecida, "
          f"{sum(1 for l in leads if not l['d'])} SEM data reconhecida)", file=sys.stderr)
    if bad_date_samples:
        print(f"  [diagnóstico] exemplos de 'Data/Hora' NÃO reconhecida (formato inesperado): "
              f"{bad_date_samples}", file=sys.stderr)
    if unmatched:
        print(f"  {unmatched} lead(s) da planilha Leads com 'Origem (anúncio)' "
              f"preenchida mas SEM anúncio correspondente na Meta Ads (entram "
              f"nos totais como \"(sem campanha)\").", file=sys.stderr)
        print(f"  [diagnóstico] exemplos de 'Origem (anúncio)' sem correspondência: "
              f"{unmatched_samples}", file=sys.stderr)
        print(f"  [diagnóstico] Ad Name conhecidos no Meta Ads (sub-funil Quiz/LEAD): "
              f"{sorted({v['ad'] for v in ad_camp_adset.values()})}", file=sys.stderr)

    dates = sorted({d for d in ([l["d"] for l in leads if l["d"]] + [m["d"] for m in meta if m["d"]])})
    now_brt = datetime.now(BRT)
    return {
        "build": {
            "generated_at_brt": now_brt.strftime("%d/%m/%Y %H:%M"),
            "build_id": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
            "today": now_brt.strftime("%Y-%m-%d"),
            "date_min": dates[0] if dates else None,
            "date_max": dates[-1] if dates else None,
            "tax_factor": TAX_FACTOR,
            "has_pv": has_pv,
            "has_chk": has_chk,
            # config da aba Relatório (lida pelo front)
            "sample_min_spend": SAMPLE_MIN_SPEND,
            "sample_min_mqls": SAMPLE_MIN_MQLS,
            "top_ads_n": TOP_ADS_N,
            # metas & parâmetros (defaults do painel editável; None = não definida)
            "meta_cpmql": META_CPMQL,
            "meta_cac": META_CAC,
            "volume_min_amostral": VOLUME_MIN_AMOSTRAL,
            "n_dias_corte": N_DIAS_CORTE,
        },
        "leads": leads,
        "meta": meta,
        # Sem fonte de vendas/faturamento nesta fase — Vendas/CAC/ROAS aparecem "-".
        "sales": [],
        # Sem coluna de permalink do criativo nesta conta.
        "ad_links": {},
        # Insights de Tráfego (texto pré-escrito, lido de relatorios.json). Preenchido
        # em main() via load_briefings(); fica {} se relatorios.json não existir.
        "briefings": {},
    }


# --------------------------------------------------------------------------- #
# Insights de Tráfego (aba Relatório)
# --------------------------------------------------------------------------- #
def load_briefings(path: str) -> dict:
    """Lê build/relatorios.json. Estrutura:
        {"generated_at": "...", "periodos": {"<preset>": {"html": "..."}, ...}}
    Retorna o dict inteiro (ou {} se o arquivo não existir/for inválido).
    A geração NÃO acontece aqui — este build só lê o texto já pronto, sem
    chamar nenhuma API (custo zero no build/no navegador)."""
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else {}
    except (ValueError, OSError):
        return {}


# --------------------------------------------------------------------------- #
# Render
# --------------------------------------------------------------------------- #
def render(data, template_path):
    # A dashboard e montada a partir de arquivos separados (visual x logica):
    #   template.html          -> esqueleto HTML (placeholders __STYLES__/__APP_JS__)
    #   identidade-visual.css  -> TODAS as cores (edite aqui p/ mexer so em cor)
    #   estilos.css            -> layout/componentes
    #   app.js                 -> logica + renderizacao
    # Esta funcao so COSTURA os arquivos e injeta os dados; nao altera nada deles.
    base = os.path.dirname(os.path.abspath(template_path))

    def readf(name):
        with open(os.path.join(base, name), "r", encoding="utf-8") as f:
            return f.read()

    with open(template_path, "r", encoding="utf-8") as f:
        tpl = f.read()
    styles = readf("identidade-visual.css") + "\n" + readf("estilos.css")
    tpl = tpl.replace("__STYLES__", styles)
    tpl = tpl.replace("__APP_JS__", readf("app.js"))
    tpl = tpl.replace("__DATA_JSON__", json.dumps(data, ensure_ascii=False))
    tpl = tpl.replace("__BUILD_ID__", data["build"]["build_id"])
    tpl = tpl.replace("__GENERATED_BRT__", data["build"]["generated_at_brt"])
    return tpl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meta-file", help="CSV local da aba Meta Ads (Página 1)")
    ap.add_argument("--leads-file", help="CSV local da aba Leads")
    ap.add_argument("--template", default="build/template.html")
    ap.add_argument("--out", default="dist/index.html")
    args = ap.parse_args()

    meta_rows = load_rows(EXPORT_URL.format(sid=SPREADSHEET_ID_META, gid=GID_META), args.meta_file)
    leads_rows = load_rows(EXPORT_URL.format(sid=SPREADSHEET_ID_LEADS, gid=GID_LEADS), args.leads_file)

    data = process(meta_rows, leads_rows)

    # Insights de Tráfego (texto pré-escrito) — lidos do arquivo versionado ao
    # lado do template. Sem chamada de API no build.
    briefings_path = os.path.join(os.path.dirname(os.path.abspath(args.template)), "relatorios.json")
    data["briefings"] = load_briefings(briefings_path)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(render(data, args.template))

    b = data["build"]
    q = sum(l["q"] for l in data["leads"])
    cv_total = sum(m["cv"] for m in data["meta"])
    print("== build ok ==", file=sys.stderr)
    print(f"  periodo        : {b['date_min']} -> {b['date_max']}", file=sys.stderr)
    print(f"  leads (Quiz)   : {len(data['leads'])}  MQLs (Nível Intenso): {q}", file=sys.stderr)
    print(f"  conversas WPP  : {cv_total:.0f} (Messaging Conversations Started, sub-funil ENGJ)", file=sys.stderr)
    print(f"  meta           : {len(data['meta'])} linhas", file=sys.stderr)
    print(f"  out            : {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
