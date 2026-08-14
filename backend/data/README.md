# Dataset de risco materno

O pipeline usa exclusivamente o arquivo
`raw/maternal_health_risk.csv`, obtido do dataset Kaggle
[ML-Ready Maternal Health Risk Assessment Dataset](https://www.kaggle.com/datasets/arshmankhalid/ml-ready-maternal-health-risk-assessment-dataset).
O treinamento não acessa a rede e não modifica esse arquivo.

## Integridade e contrato

- SHA-256: `1d272d463635f9d4b94f268468253c9dbe1e78e576ee8badb1b773f4d749a752`.
- Cabeçalho real: `Age`, `SystolicBP`, `DiastolicBP`, `Blood glucose`,
  `BodyTemp`, `HeartRate`, `RiskLevel`.
- Atributos internos: `age`, `systolic_bp`, `diastolic_bp`, `blood_sugar`,
  `body_temperature`, `heart_rate`.
- Alvo: `RiskLevel`, com `0=low`, `1=mid` e `2=high`.
- Não há valores ausentes no CSV fornecido. Mesmo assim, os dois pipelines contêm
  imputação pela mediana, ajustada somente no conjunto de treino.

## Auditoria e preparo

O arquivo contém **1.014 registros**, um a mais que os 1.013 anunciados na
descrição recebida. A distribuição bruta é `low=406`, `mid=336`, `high=272`.
Há somente **452 linhas integralmente únicas**: 562 ocorrências são repetições
exatas. O pipeline elimina essas repetições antes da separação, resultando em
`low=234`, `mid=106`, `high=112`.

Após essa remoção, existem 416 vetores distintos de atributos e 35 grupos nos
quais o mesmo vetor possui rótulos diferentes. Esses conflitos não são
apagados: todos os registros de um vetor ficam no mesmo grupo durante o
`StratifiedGroupKFold`, impedindo que uma medição idêntica apareça nos dois
lados do holdout. Essa é uma estratificação aproximada em 80/20; dentre os
cinco folds, escolhe-se deterministicamente o que mais se aproxima do tamanho
e da distribuição globais, sem consultar resultados dos modelos.

O valor `HeartRate=7` ocorre duas vezes no arquivo bruto (linhas físicas 501 e
910, incluindo o cabeçalho) e é um extremo estatístico. Ele é registrado no
relatório e mantido: o dataset não oferece prontuário, unidade alternativa ou
regra verificável que autorize corrigi-lo ou descartá-lo.

## Modelagem reproduzível

São comparados exatamente dois modelos, ambos com `class_weight="balanced"`:

1. regressão logística multinomial, com imputação e padronização;
2. random forest, com imputação e 300 árvores.

A escolha maximiza primeiro o recall da classe `high`, para reduzir falsos
negativos de alto risco; F1 macro e acurácia são desempates, nessa ordem. O
relatório inclui acurácia, precisão/recall/F1 macro, recall de cada classe,
matriz de confusão e número de falsos negativos de alto risco. Após a
comparação no holdout, somente o modelo escolhido é reajustado nas 452 linhas
únicas e serializado.

Na raiz de `backend/`, com Python 3.12 ou posterior:

```bash
python -m pip install -e '.[dev]'
python -m training.train \
  --data data/raw/maternal_health_risk.csv \
  --output-dir artifacts \
  --model-version 1.0.0
pytest tests/test_ml.py
```

Dependências do pipeline: `pandas`, `numpy` (transitiva), `scikit-learn`,
`joblib` e, somente para testes, `pytest`. O treinamento usa semente 42. Gera
`artifacts/maternal_risk_model_v1.0.0.joblib` e
`artifacts/training_report_v1.0.0.json`.

## Explicabilidade e limitações

A importância global usa a importância de impureza da floresta ou a média
macro do valor absoluto dos coeficientes logísticos, sempre normalizada. Cada
predição tem uma decomposição exata e sem dependência de SHAP: diferenças de
probabilidade ao longo dos caminhos das árvores, ou termos lineares do logit
multinomial. O resultado informa o erro de reconstrução para tornar a
explicação verificável.

O CSV não possui identificador de paciente, origem temporal, idade gestacional,
histórico, desfecho clínico nem contexto de coleta. Portanto, não é possível
saber se duplicatas representam a mesma pessoa, medições repetidas ou pessoas
distintas. A descrição fornecida atribui os dados a hospitais, clínicas e
centros maternos de áreas rurais de Bangladesh, mas o CSV não traz metadados que
permitam auditar essa origem. Não é possível validar causalidade, desempenho
longitudinal ou generalização para a população brasileira. O modelo classifica
apenas o padrão desse dataset e deve ser usado como apoio à triagem profissional,
nunca como diagnóstico ou decisão clínica automática.
