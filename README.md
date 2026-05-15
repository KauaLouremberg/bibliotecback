# bibliotecback

API Django + Django Ninja + JWT (`djangorestframework-simplejwt`).

## Arranque

```bash
cd bibliotecback
. .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

Endpoints: `/api/auth/register`, `/api/auth/login`, `/api/auth/refresh`, `/api/auth/me`.

Ver também o `README.md` na raiz do repositório pai.
