from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from routers.shipgate import router as shipgate_router

app = FastAPI(title=settings.app_name, version='1.0.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

@app.get('/')
def root():
    return {'ok': True, 'service': 'shipgate', 'docs': '/docs'}

@app.get('/health')
def health_root():
    return {'ok': True, 'service': 'shipgate'}

@app.get('/__routes')
def routes_debug():
    return {'loaded_main': __file__, 'routes': sorted([getattr(route, 'path', '') for route in app.routes])}

app.include_router(shipgate_router)
