from ninja import NinjaAPI

from accounts.api import router as auth_router
from library.api import router as library_router

api = NinjaAPI(title="Bibliotec API", version="1.0.0", urls_namespace="api")

api.add_router("/auth/", auth_router)
api.add_router("/library/", library_router)
