from __future__ import annotations

from dataclasses import dataclass

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.core.config import Settings
from app.schemas import ProtocolSource


@dataclass(frozen=True)
class ExplanationResult:
    text: str
    llm_used: bool
    llm_model: str | None


SYSTEM_PROMPT = """
Você é um assistente informacional para profissionais que fazem triagem de risco materno.
Use somente a predição fornecida e as sínteses rastreáveis dos documentos oficiais abaixo.

Regras obrigatórias:
- escreva em português do Brasil, com linguagem clara e objetiva;
- explique o resultado como apoio à triagem, nunca como diagnóstico;
- não prescreva medicamentos, exames ou tratamentos;
- não tome decisão clínica nem substitua avaliação profissional;
- não invente critérios ou fatos ausentes nos excertos;
- quando a informação for insuficiente, diga isso explicitamente;
- diferencie a classificação estatística do modelo das orientações documentais;
- os dados não incluem idade gestacional, sintomas, histórico, jejum ou momento da glicemia;
  não aplique automaticamente critérios que dependam dessas informações ausentes;
- cite as fontes no texto usando [1], [2] e assim por diante;
- diante de sinais de alerta presentes no contexto, apenas reproduza a orientação de busca de
  atendimento contida na fonte, sem criar uma conduta nova.
""".strip()


class ProtocolExplainer:
    def __init__(self, settings: Settings) -> None:
        self._model_name = settings.openai_model
        self._enabled = bool(
            settings.openai_api_key and settings.openai_api_key.get_secret_value().strip()
        )
        self._chain = None
        if self._enabled:
            llm = ChatOpenAI(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
                timeout=settings.llm_timeout_seconds,
                max_retries=2,
            )
            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", SYSTEM_PROMPT),
                    (
                        "human",
                        "Predição do modelo:\n{prediction}\n\n"
                        "Fatores explicativos:\n{factors}\n\n"
                        "Pergunta do profissional:\n{question}\n\n"
                        "Sínteses rastreáveis recuperadas:\n{documents}\n\n"
                        "Produza uma explicação curta, responsável e fundamentada.",
                    ),
                ]
            )
            self._chain = prompt | llm | StrOutputParser()

    @property
    def is_configured(self) -> bool:
        return self._enabled

    def explain(
        self,
        *,
        prediction: str,
        factors: str,
        question: str | None,
        sources: list[ProtocolSource],
    ) -> ExplanationResult:
        if not self._enabled or self._chain is None:
            return ExplanationResult(
                text=(
                    "A classificação de apoio foi calculada pelo modelo de Machine Learning e os "
                    "protocolos relacionados foram recuperados. A explicação por LLM não foi "
                    "executada porque GUARDIA_OPENAI_API_KEY não está configurada. Consulte as "
                    "fontes exibidas e mantenha a decisão com o profissional responsável."
                ),
                llm_used=False,
                llm_model=None,
            )

        documents = "\n\n".join(
            f"[{index}] {source.title} — {source.reference}\n{source.excerpt}\nFonte: {source.url}"
            for index, source in enumerate(sources, start=1)
        )
        text = self._chain.invoke(
            {
                "prediction": prediction,
                "factors": factors,
                "question": question or "Explique a classificação e os fatores mais relevantes.",
                "documents": documents,
            }
        )
        return ExplanationResult(text=text.strip(), llm_used=True, llm_model=self._model_name)
