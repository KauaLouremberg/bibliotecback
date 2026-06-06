# Deploy — Supabase + Render (plano gratuito)

## Visão geral

| Peça | Serviço |
|------|---------|
| PostgreSQL | **Supabase** — projeto `Acervo Digital` |
| API + WebSocket | **Render** — web service `acervo-api` |
| Redis (chat) | **Render Key Value** — `acervo-redis` (via `render.yaml`) |

## 1. Supabase (banco)

Projeto já criado: **Acervo Digital** (`lcwqriuenyubloalczsu`).

1. [Supabase Dashboard](https://supabase.com/dashboard/project/lcwqriuenyubloalczsu/settings/database) → **Database** → **Connection string**
2. Escolha **URI** e **Session pooler** (porta **5432**)
3. Copie a URL e garanta `?sslmode=require` no final

Exemplo:

```
postgresql://postgres.lcwqriuenyubloalczsu:[SUA-SENHA]@aws-0-us-east-2.pooler.supabase.com:5432/postgres?sslmode=require
```

O schema Django já foi aplicado via migrations no Supabase. Novas migrations locais:

```bash
python manage.py migrate
# ou aplique o SQL via Supabase MCP / Dashboard
```

## 2. Render (backend)

### Passo a passo (agora)

O `render.yaml` já está no GitHub (`main`). Siga:

1. **Conectar GitHub ao Render** (se ainda não fez): https://dashboard.render.com → Account Settings → GitHub
2. **Abrir o Blueprint** (link direto):
   https://dashboard.render.com/blueprint/new?repo=https://github.com/KauaLouremberg/bibliotecback
3. Autorize o repositório se pedido
4. **Obrigatório:** preencha **`DATABASE_URL`** antes do deploy (secret vazio = build/start falha)
   - Supabase → Database → Connection string → **URI** → **Session pooler** (5432)
   - Exemplo: `postgresql://postgres.lcwqriuenyubloalczsu:[SENHA]@aws-0-us-east-2.pooler.supabase.com:5432/postgres?sslmode=require`
5. Clique **Apply**
   - `acervo-api` (web, Python, free)
   - `acervo-redis` (Key Value, free)
6. Se o serviço já existir sem `DATABASE_URL`: **Environment** → adicione → **Manual Deploy**
7. Aguarde deploy **Live** (~5–10 min na primeira vez)
8. Teste: `https://acervo-api.onrender.com/api/health`

### Plugin MCP Render no Cursor (opcional, para eu gerenciar daqui)

1. Crie uma API key: https://dashboard.render.com/u/settings#api-keys
2. Copie [`.cursor/mcp.render.example.json`](.cursor/mcp.render.example.json) para `~/.cursor/mcp.json` (ou adicione o bloco `render` ao arquivo existente)
3. Troque `COLE_SUA_API_KEY_AQUI` por `rnd_...`
4. **Reinicie o Cursor** e peça: *“cria o serviço no Render”*

### Opção A — Blueprint (recomendado)

1. Faça push do `render.yaml` para `https://github.com/KauaLouremberg/bibliotecback`
2. Abra: https://dashboard.render.com/blueprint/new?repo=https://github.com/KauaLouremberg/bibliotecback
3. Ao aplicar o Blueprint, preencha **`DATABASE_URL`** com a URI do Supabase
4. Aguarde o deploy ficar **Live**

URL da API: `https://acervo-api.onrender.com` (ou o nome que escolher)

Health check: `GET https://acervo-api.onrender.com/api/health` → `{"status":"ok"}`

### Opção B — Plugin MCP Render

Configure a API key em Cursor (`~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "render": {
      "url": "https://mcp.render.com/mcp",
      "headers": {
        "Authorization": "Bearer rnd_..."
      }
    }
  }
}
```

Reinicie o Cursor e peça para criar o serviço a partir do repositório.

## 3. Variáveis de ambiente (Render)

| Variável | Valor |
|----------|--------|
| `DATABASE_URL` | URI do Supabase (Session pooler, `sslmode=require`) |
| `DJANGO_SECRET_KEY` | Gerada pelo Render (`generateValue`) |
| `DJANGO_DEBUG` | `0` |
| `DJANGO_ALLOWED_HOSTS` | `.onrender.com` |
| `REDIS_URL` | Preenchida pelo Key Value `acervo-redis` |
| `CORS_ALLOWED_ORIGINS` | (opcional) origens do Expo em produção |

## 4. App Expo (celular)

Em `bibliotecfront/.env`:

```
EXPO_PUBLIC_API_URL=https://acervo-api.onrender.com
```

Reinicie o Metro: `pnpm start -- --clear`

WebSocket usa a mesma URL (`http` → `ws`).

## Limitações do plano gratuito

- Render **dorme** após ~15 min sem uso (primeira requisição demora)
- Uploads em `media/` **não persistem** no Render (avatares somem no redeploy)
- Supabase free: pausa após inatividade prolongada

## Segurança Supabase

As tabelas Django estão no schema `public`. O Supabase expõe esse schema via PostgREST se alguém usar a **anon key** no client. Este app usa **Django + JWT** (não Supabase Auth). Para reduzir exposição, evite usar `@supabase/supabase-js` contra essas tabelas ou ative RLS com políticas restritivas.
