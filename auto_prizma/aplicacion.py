"""Instancia de la aplicacion FastAPI compartida por todas las rutas.
"""

from fastapi import FastAPI


app = FastAPI(
    title="Cargue Prizma Pro"
)
