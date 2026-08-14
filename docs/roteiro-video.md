# Roteiro do vídeo de demonstração

Duração máxima exigida: 15 minutos. Publicação: YouTube ou Vimeo, pública ou não listada.

## Sequência sugerida

1. **Problema e limites — 1 min**
   - Apresentar a triagem de risco materno.
   - Explicar que a decisão é humana e que a aplicação não diagnostica nem prescreve.
2. **Dados e modelos — 3 min**
   - Mostrar origem e seis atributos do dataset.
   - Explicar duplicatas, split agrupado e comparação entre regressão logística e random forest.
   - Mostrar por que recall de alto risco foi priorizado.
3. **Arquitetura — 2 min**
   - Mostrar frontend e backend separados.
   - Explicar o fluxo LangChain: ML → RAG → LLM → auditoria.
4. **Jornada completa — 6 min**
   - Preencher os seis valores e uma pergunta profissional.
   - Executar a análise.
   - Mostrar classe e probabilidades, contribuições, explicação, fontes e aviso de responsabilidade.
   - Abrir o histórico e consultar a mesma análise pelo identificador.
5. **RAG e responsabilidade — 2 min**
   - Mostrar as fontes oficiais e a resposta restrita aos documentos recuperados.
   - Demonstrar a mensagem explícita quando a chave da LLM não está configurada.
6. **Limitações e encerramento — 1 min**
   - Destacar tamanho do dataset, origem em Bangladesh, rótulos conflitantes e ausência de validação clínica.

Antes de gravar, executar `docker compose up --build`, configurar `OPENAI_API_KEY` e conferir a jornada em `http://localhost:8080`.

