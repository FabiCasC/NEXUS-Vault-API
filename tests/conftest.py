"""
tests/conftest.py

Los tests NUNCA deben golpear servicios externos reales (OpenAI, Portal),
así el .env tenga credenciales reales cargadas (USE_LLM=1, API_EDUCACION_*).
Esto evita:
  - gastar cuota real de OpenAI en cada corrida de pytest,
  - publicar actividad de prueba en el canal real de Portal,
  - tests lentos/no deterministas por depender de la red.

Este archivo se importa ANTES que cualquier test module en esta carpeta
(pytest carga conftest.py primero). Fijamos estas variables a nivel de
módulo -no dentro de un fixture- para que ya estén puestas cuando
backend/api.py haga load_dotenv() al importarse (load_dotenv() no
sobreescribe variables que ya existen en el entorno).
"""

import os

os.environ["USE_LLM"] = "0"
os.environ["PORTAL_SECRET"] = ""
os.environ["API_EDUCACION_SECRET"] = ""
