# Guardiã AI — frontend

Interface React + TypeScript para a triagem de risco materno. O frontend consome o backend pelo prefixo `/api` e não contém regras de classificação.

## Desenvolvimento

Requisitos: Node.js 22 e npm.

```bash
npm install
npm run dev
```

Por padrão, o Vite encaminha `/api` para `http://localhost:8000`. O destino pode ser alterado com `VITE_DEV_API_TARGET`.

## Verificações

```bash
npm test
npm run build
```

## Container

```bash
docker build -t guardia-ai-frontend .
docker run --rm -p 8080:80 guardia-ai-frontend
```

O nginx entrega a SPA e encaminha `/api` para `http://backend:8000`. Em Docker Compose, o serviço do backend deve se chamar `backend`.
