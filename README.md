# bibliotecback

API Django + Django Ninja + JWT (`djangorestframework-simplejwt`).

## Arranque

Requisitos: PostgreSQL (`.env`) e **Redis** para o chat em tempo real.

```bash
# Redis (Manjaro)
sudo systemctl start redis
redis-cli ping   # PONG
```

```bash
cd bibliotecback
. .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --reload
```

Defina no `.env`:

```
REDIS_URL=redis://127.0.0.1:6379/0
```

Endpoints: `/api/auth/register`, `/api/auth/login`, `/api/auth/refresh`, `/api/auth/me`, `/api/library/chats`, WebSocket `ws://HOST:8000/ws/chats/{thread_id}/?token=JWT`.

Ver também o `README.md` na raiz do repositório pai.
