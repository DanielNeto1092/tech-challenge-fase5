"""Gera o relatório técnico obrigatório a partir dos artefatos auditáveis."""

from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT_DATA = ROOT / "backend" / "artifacts" / "training_report_v1.0.0.json"
OUTPUT = ROOT / "docs" / "relatorio-tecnico.pdf"

NAVY = colors.HexColor("#18344A")
TEAL = colors.HexColor("#148A85")
PALE_TEAL = colors.HexColor("#E8F5F3")
INK = colors.HexColor("#24333D")
MUTED = colors.HexColor("#5E6D75")
LIGHT = colors.HexColor("#EFF3F4")
HIGH = colors.HexColor("#A13D4A")


def _register_fonts() -> tuple[str, str]:
    regular = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    bold = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    if regular.exists() and bold.exists():
        pdfmetrics.registerFont(TTFont("DejaVu", regular))
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", bold))
        return "DejaVu", "DejaVu-Bold"
    return "Helvetica", "Helvetica-Bold"


FONT, FONT_BOLD = _register_fonts()


def _styles():
    sample = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "Title",
            parent=sample["Title"],
            fontName=FONT_BOLD,
            fontSize=24,
            leading=29,
            textColor=NAVY,
            alignment=TA_CENTER,
            spaceAfter=18,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=sample["Normal"],
            fontName=FONT,
            fontSize=12,
            leading=18,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceAfter=12,
        ),
        "h1": ParagraphStyle(
            "H1",
            parent=sample["Heading1"],
            fontName=FONT_BOLD,
            fontSize=16,
            leading=20,
            textColor=NAVY,
            spaceBefore=14,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=sample["Heading2"],
            fontName=FONT_BOLD,
            fontSize=12,
            leading=16,
            textColor=TEAL,
            spaceBefore=10,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=sample["BodyText"],
            fontName=FONT,
            fontSize=9.2,
            leading=14,
            textColor=INK,
            spaceAfter=7,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=sample["BodyText"],
            fontName=FONT,
            fontSize=7.4,
            leading=10,
            textColor=INK,
        ),
        "callout": ParagraphStyle(
            "Callout",
            parent=sample["BodyText"],
            fontName=FONT_BOLD,
            fontSize=9.4,
            leading=14,
            textColor=NAVY,
            borderColor=TEAL,
            borderWidth=1,
            borderPadding=9,
            backColor=PALE_TEAL,
            spaceBefore=8,
            spaceAfter=10,
        ),
    }


STYLES = _styles()


def p(text: str, style: str = "body") -> Paragraph:
    return Paragraph(text, STYLES[style])


def bullet(text: str) -> Paragraph:
    return Paragraph(f"• {text}", STYLES["body"])


def _page(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#D8E1E4"))
    canvas.line(2 * cm, 1.45 * cm, 19 * cm, 1.45 * cm)
    canvas.setFont(FONT, 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(2 * cm, 1 * cm, "Guardiã AI — Relatório técnico")
    canvas.drawRightString(19 * cm, 1 * cm, f"Página {doc.page}")
    canvas.restoreState()


def _table(rows, widths, *, header=True, font_size=7.5) -> Table:
    table = Table(rows, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("FONTNAME", (0, 0), (-1, -1), FONT),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("LEADING", (0, 0), (-1, -1), font_size + 3),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C9D5D9")),
        ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [colors.white, LIGHT]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if header:
        commands.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
            ]
        )
    table.setStyle(TableStyle(commands))
    return table


def _pct(value: float) -> str:
    return f"{value * 100:.2f}%".replace(".", ",")


def _metric_rows(report: dict) -> list[list[str]]:
    rows = [
        [
            "Modelo",
            "Accuracy",
            "Precision macro",
            "Recall macro",
            "F1 macro",
            "Recall alto",
        ]
    ]
    labels = {
        "multinomial_logistic_regression": "Regressão logística",
        "random_forest": "Random forest",
    }
    for model_name in report["candidate_models"]:
        metrics = report["evaluations"][model_name]
        rows.append(
            [
                labels[model_name],
                _pct(metrics["accuracy"]),
                _pct(metrics["precision_macro"]),
                _pct(metrics["recall_macro"]),
                _pct(metrics["f1_macro"]),
                _pct(metrics["recall_by_class"]["high"]),
            ]
        )
    return rows


def build_story(report: dict) -> list:
    audit = report["dataset"]["audit"]
    selected = report["evaluations"][report["selected_model"]]
    story = [
        Spacer(1, 3.1 * cm),
        p("GUARDIÃ AI", "title"),
        p("Apoio à triagem de risco materno", "subtitle"),
        Spacer(1, 0.35 * cm),
        p("Relatório técnico — Tech Challenge Fase 5", "subtitle"),
        p("Dados + Machine Learning + LLM + RAG + aplicação", "callout"),
        Spacer(1, 1.1 * cm),
        p(
            "Versão 1.0.0<br/>Gerado em 14 de agosto de 2026<br/>"
            "Cenário: saúde da mulher — triagem de risco durante a gestação",
            "subtitle",
        ),
        PageBreak(),
        p("1. Problema e objetivo", "h1"),
        p(
            "A Guardiã AI recebe seis indicadores de uma gestante, executa um modelo de "
            "classificação de risco, recupera sínteses rastreáveis de documentos oficiais e "
            "produz uma "
            "explicação destinada ao profissional responsável pelo atendimento. O produto "
            "implementa uma jornada completa, da entrada dos dados ao registro auditável do "
            "resultado."
        ),
        p(
            "O sistema é exclusivamente um apoio à triagem. Não realiza diagnóstico, não "
            "prescreve medicamentos e não toma decisões clínicas ou de segurança de forma "
            "automática. A decisão final permanece humana.",
            "callout",
        ),
        p("Escopo funcional", "h2"),
        bullet(
            "Formulário web para idade, pressão arterial, glicemia, temperatura e "
            "frequência cardíaca."
        ),
        bullet(
            "Comparação de dois modelos de Machine Learning e seleção por métrica justificada."
        ),
        bullet("Explicabilidade local da predição e importância global das variáveis."),
        bullet("RAG com documentos oficiais e apresentação das fontes recuperadas."),
        bullet(
            "Explicação por LLM via OpenAI, organizada no fluxo principal com LangChain."
        ),
        bullet(
            "Persistência dos dados utilizados e dos resultados para logging e auditoria."
        ),
        p("2. Dados utilizados", "h1"),
        p(
            "Foi utilizado o <i>ML-Ready Maternal Health Risk Assessment Dataset</i>, "
            "selecionado no Kaggle. A descrição atribui a coleta a hospitais, clínicas "
            "comunitárias e centros de saúde materna de áreas rurais de Bangladesh. O CSV "
            "não contém nomes nem identificadores de paciente."
        ),
        _table(
            [
                ["Campo", "Unidade", "Papel"],
                ["Age", "anos", "Atributo"],
                ["SystolicBP", "mmHg", "Atributo"],
                ["DiastolicBP", "mmHg", "Atributo"],
                ["Blood glucose", "mmol/L", "Atributo"],
                ["BodyTemp", "°F", "Atributo"],
                ["HeartRate", "bpm", "Atributo"],
                ["RiskLevel", "0 baixo; 1 médio; 2 alto", "Alvo"],
            ],
            [4.4 * cm, 4.4 * cm, 4.2 * cm],
        ),
        Spacer(1, 0.3 * cm),
        p("Auditoria do arquivo", "h2"),
        bullet(
            f"O CSV possui {audit['raw_row_count']} registros, embora a descrição pública "
            "informe 1.013."
        ),
        bullet(
            f"Foram encontradas {audit['exact_duplicate_rows_removed']} repetições exatas; "
            "restaram "
            f"{audit['unique_exact_row_count']} linhas únicas."
        ),
        bullet(
            f"Há {audit['feature_vector_groups_with_conflicting_labels']} grupos em que os mesmos "
            "atributos aparecem associados a rótulos diferentes."
        ),
        bullet(
            "O valor HeartRate=7 é um extremo estatístico. Foi mantido por falta de evidência "
            "auditável no arquivo para corrigi-lo ou removê-lo."
        ),
        bullet(f"SHA-256 do CSV: {report['dataset']['sha256']}."),
        PageBreak(),
        p("3. Preparação e separação dos dados", "h1"),
        p(
            "Os nomes das colunas foram normalizados, os atributos foram convertidos para "
            "valores numéricos e valores infinitos foram tratados como ausentes. Os pipelines "
            "contêm imputação pela mediana; o pré-processamento é ajustado somente na partição "
            "de treino."
        ),
        p(
            "As repetições exatas foram removidas antes da divisão. Vetores de atributos iguais "
            "foram mantidos no mesmo grupo por StratifiedGroupKFold, inclusive quando os "
            "rótulos eram conflitantes. Assim, nenhum vetor idêntico aparece simultaneamente "
            "no treino e no teste."
        ),
        _table(
            [
                ["Partição", "Registros", "Baixo", "Médio", "Alto", "Grupos"],
                [
                    "Treino",
                    str(report["split"]["train_row_count"]),
                    str(report["split"]["train_class_counts"]["low"]),
                    str(report["split"]["train_class_counts"]["mid"]),
                    str(report["split"]["train_class_counts"]["high"]),
                    str(report["split"]["train_feature_group_count"]),
                ],
                [
                    "Teste",
                    str(report["split"]["test_row_count"]),
                    str(report["split"]["test_class_counts"]["low"]),
                    str(report["split"]["test_class_counts"]["mid"]),
                    str(report["split"]["test_class_counts"]["high"]),
                    str(report["split"]["test_feature_group_count"]),
                ],
            ],
            [3 * cm, 2.2 * cm, 2.1 * cm, 2.1 * cm, 2.1 * cm, 2.2 * cm],
        ),
        p("4. Modelos e métricas", "h1"),
        p(
            "Foram treinados exatamente dois candidatos: regressão logística multinomial com "
            "padronização e random forest com 300 árvores. Ambos usam balanceamento de classes. "
            "A semente aleatória é 42."
        ),
        _table(
            _metric_rows(report),
            [3.5 * cm, 2.1 * cm, 2.6 * cm, 2.3 * cm, 2.1 * cm, 2.3 * cm],
            font_size=6.8,
        ),
        Spacer(1, 0.25 * cm),
        p(
            f"A random forest foi selecionada. Obteve accuracy {_pct(selected['accuracy'])}, "
            f"F1 macro {_pct(selected['f1_macro'])} e recall de alto risco "
            f"{_pct(selected['recall_by_class']['high'])}, com "
            f"{selected['high_risk_false_negatives']} falsos negativos de alto risco no holdout.",
            "callout",
        ),
        p("Por que não usar apenas accuracy?", "h2"),
        p(
            "Accuracy pode esconder desempenho fraco em classes menores. Neste cenário, deixar "
            "de identificar um registro rotulado como alto risco tem impacto potencialmente "
            "mais relevante do que aumentar a taxa global de acerto. Por isso, a regra definida "
            "antes da comparação maximiza primeiro o recall da classe alta; F1 macro e accuracy "
            "são desempates. O recall da classe média permaneceu baixo, o que limita a utilização "
            "e impede qualquer interpretação diagnóstica."
        ),
        PageBreak(),
        p("5. Explicabilidade", "h1"),
        p(
            "A importância global da random forest mostra quanto cada atributo participou das "
            "divisões das árvores. Para cada predição, o backend decompõe exatamente a variação "
            "de probabilidade ao longo do caminho percorrido em todas as árvores. A soma da base "
            "e das contribuições reconstrói a probabilidade, com erro numérico registrado."
        ),
        _table(
            [["Atributo", "Importância global"]]
            + [
                [feature, _pct(value)]
                for feature, value in report["global_feature_importance"].items()
            ],
            [7 * cm, 5 * cm],
        ),
        p(
            "Contribuição não significa causalidade. Ela explica o comportamento do modelo no "
            "dataset treinado e não prova que uma variável causou determinado desfecho clínico.",
            "callout",
        ),
        p("6. Arquitetura da aplicação", "h1"),
        _table(
            [
                ["Componente", "Responsabilidade"],
                [
                    "Frontend React/TypeScript",
                    "Coleta, validação, resultados, fontes e histórico.",
                ],
                [
                    "API FastAPI",
                    "Contrato HTTP, validação e composição dos casos de uso.",
                ],
                [
                    "Pipeline scikit-learn",
                    "Predição, probabilidades e explicabilidade.",
                ],
                ["LangChain", "Orquestra ML → recuperação → explicação."],
                ["Retriever TF-IDF", "Busca lexical local nas sínteses oficiais."],
                [
                    "OpenAI gpt-5.6-luna",
                    "Explica resultado e contexto recuperado quando há chave.",
                ],
                ["SQLite", "Registra entrada, resultado, modelo, fontes e uso da LLM."],
            ],
            [5.2 * cm, 10.5 * cm],
        ),
        p(
            "Frontend e backend são projetos separados, com Dockerfiles próprios. O Docker "
            "Compose conecta os containers e preserva o banco de auditoria em volume. A ausência "
            "de chave OpenAI não interrompe ML e RAG: a API marca llm_used=false e informa que a "
            "explicação por LLM não foi executada."
        ),
        p("7. LLM e RAG", "h1"),
        p(
            "O modelo padrão configurável é gpt-5.6-luna. O prompt delimita a predição, os "
            "fatores e as sínteses recuperadas, exige português do Brasil, proíbe diagnóstico e "
            "prescrição, solicita indicação [1], [2] das fontes e obriga declarar insuficiência "
            "de informação. A chave é fornecida somente por variável de ambiente."
        ),
        p(
            "Quando a LLM está habilitada, classificação, probabilidades, seis valores com "
            "suas contribuições, pergunta livre e sínteses recuperadas são enviados à OpenAI."
        ),
        KeepTogether(
            [
                p("Base oficial", "h2"),
                _table(
                    [
                        ["Documento", "Versão", "Uso no RAG"],
                        [
                            "Caderneta Brasileira da Gestante",
                            "MS, 2026",
                            "Alertas, PA e acompanhamento.",
                        ],
                        [
                            "Manual de Gestação de Alto Risco",
                            "MS, 2022",
                            "Estratificação, PA, glicemia e contexto.",
                        ],
                        [
                            "Linha de Cuidado do Pré-natal",
                            "MS/SAPS, 2021",
                            "Planejamento e situações de urgência.",
                        ],
                        [
                            "Cuidados Obstétricos em DMG",
                            "MS/OPAS/FEBRASGO/SBD, 2021",
                            "Contexto do monitoramento glicêmico.",
                        ],
                    ],
                    [5.8 * cm, 4.5 * cm, 5.4 * cm],
                    font_size=6.9,
                ),
                p(
                    "A recuperação é local e determinística por TF-IDF. Cada resultado inclui "
                    "título, página ou seção, URL oficial, síntese e pontuação de relevância. "
                    "Os documentos integrais não são redistribuídos."
                ),
            ]
        ),
        p("8. Segurança, responsabilidade e auditoria", "h1"),
        bullet(
            "Toda tela e resposta declara que o sistema é apoio e não substitui decisão humana."
        ),
        bullet(
            "O prompt proíbe diagnóstico definitivo, prescrição e recomendação sem base documental."
        ),
        bullet("Campos de identificação pessoal não são coletados."),
        bullet(
            "A interface orienta a não inserir identificadores no campo livre de pergunta."
        ),
        bullet(
            "Entradas fora do domínio observado pelo modelo são recusadas pelo contrato da API."
        ),
        bullet(
            "Cada análise recebe UUID e data UTC e persiste os dados utilizados e o resultado."
        ),
        bullet(
            "O log registra versão do modelo, probabilidades, contribuições, fontes e uso da LLM."
        ),
        bullet(
            "Falha da LLM gera resposta segura e explícita; não há substituição silenciosa "
            "por texto inventado."
        ),
        p("9. Limitações", "h1"),
        bullet("Após remover repetições exatas, restam apenas 452 registros."),
        bullet("O mesmo vetor aparece com rótulos conflitantes em 35 grupos."),
        bullet(
            "O dataset não fornece paciente, tempo, idade gestacional, sintomas, histórico "
            "ou desfecho."
        ),
        bullet(
            "A origem em Bangladesh não demonstra generalização para a população brasileira."
        ),
        bullet("BodyTemp usa °F; os protocolos brasileiros usam °C."),
        bullet(
            "Glicemia não informa jejum, pós-prandial ou TOTG e não sustenta critérios "
            "diagnósticos."
        ),
        bullet("HeartRate=7 foi mantido como dado extremo não verificável."),
        bullet(
            "Recall médio de 33,33% e F1 macro de 65,37% demonstram desempenho limitado."
        ),
        bullet(
            "A LLM pode errar; sua resposta fica restrita ao contexto recuperado e exige "
            "revisão humana."
        ),
        bullet(
            "O protótipo não possui autenticação: não deve ser exposto à internet nem receber "
            "dados reais ou identificáveis."
        ),
        bullet(
            "Fontes CC BY-NC-SA exigem atribuição, uso não comercial e compartilhamento compatível."
        ),
        p(
            "Por essas limitações, a solução é uma demonstração acadêmica. Não foi validada "
            "clinicamente e não deve ser implantada em atendimento real sem governança, revisão "
            "especializada, avaliação ética, segurança da informação e validação prospectiva.",
            "callout",
        ),
        p("10. Reprodução e entregáveis", "h1"),
        p(
            "O repositório contém código-fonte, script de treinamento, dataset auditado, artefato "
            "versionado, métricas em JSON, frontend, backend, testes, Dockerfiles, Docker Compose, "
            "README e este relatório. O treinamento pode ser repetido com <font name='Courier'>"
            "python -m training.train</font>. A jornada pode ser executada por containers após "
            "configurar OPENAI_API_KEY."
        ),
        p("Referências principais", "h2"),
        p(
            "Dataset Kaggle: https://www.kaggle.com/datasets/arshmankhalid/"
            "ml-ready-maternal-health-risk-assessment-dataset"
        ),
        p("UCI/DOI: https://doi.org/10.24432/C5DP5D"),
        p(
            "Caderneta 2026: https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/"
            "s/saude-da-mulher/publicacoes/caderneta-brasileira-da-gestante.pdf/view"
        ),
        p(
            "Manual de Alto Risco: https://bvsms.saude.gov.br/bvs/publicacoes/manual_gestacao_alto_risco.pdf"
        ),
        p(
            "Linha de Cuidado: https://linhasdecuidado.saude.gov.br/portal/pre-natal-baixo-risco/"
        ),
        p(
            "Manual DMG: https://bvsms.saude.gov.br/bvs/publicacoes/"
            "cuidados_obstetricos_diabetes_gestacional_brasil.pdf"
        ),
        p("OpenAI models: https://developers.openai.com/api/docs/models"),
    ]
    return story


def main() -> int:
    report = json.loads(REPORT_DATA.read_text(encoding="utf-8"))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    document = BaseDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title="Guardiã AI — Relatório técnico",
        author="Equipe Guardiã AI",
        subject="Tech Challenge Fase 5 — Triagem de risco materno",
        creator="docs/generate_report.py",
    )
    frame = Frame(
        document.leftMargin, document.bottomMargin, document.width, document.height
    )
    document.addPageTemplates([PageTemplate(id="report", frames=[frame], onPage=_page)])
    document.build(build_story(report))
    print(f"Relatório gerado: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
