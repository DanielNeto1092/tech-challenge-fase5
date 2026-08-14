# Artefatos de ML

O comando documentado em `backend/data/README.md` grava aqui dois arquivos
versionados:

- `maternal_risk_model_v<versao>.joblib`: estimador, contrato de atributos,
  rótulos, versões de bibliotecas, métricas e auditoria do treino;
- `training_report_v<versao>.json`: exploração, split, comparação dos dois
  modelos, justificativa da seleção e importância global.

Arquivos Joblib usam pickle internamente. A aplicação deve carregar somente o
artefato gerado pelo pipeline e nunca aceitar um arquivo enviado por usuário.

