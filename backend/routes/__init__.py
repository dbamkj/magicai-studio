"""MagiCAi Studio — FastAPI routes (per-domain routers).

Future work: split endpoints from server.py into /routes/{auth,projects,imagegen,videogen,multishot,faceswap,headswap,lipsync,redub,meta}.py
Each module will expose an APIRouter and be included from server.py's main api_router.
"""
