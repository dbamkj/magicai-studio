"""Central config — ENV flag (DEV|BETA|PROD), DB selection, JWT, admin email.
All other modules import from here.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

ENV = os.environ.get('ENV', 'DEV').upper()
if ENV not in ('DEV', 'BETA', 'PROD'):
    ENV = 'DEV'

_DB_NAME_MAP = {
    'DEV': os.environ.get('DB_NAME_DEV') or os.environ.get('DB_NAME', 'videoai_database'),
    'BETA': os.environ.get('DB_NAME_BETA', 'magicai_beta'),
    'PROD': os.environ.get('DB_NAME_PROD', 'magicai_prod'),
}

MONGO_URL = os.environ['MONGO_URL']
DB_NAME = _DB_NAME_MAP[ENV]
UPLOAD_DIR = ROOT_DIR / 'uploads'
UPLOAD_DIR.mkdir(exist_ok=True)

JWT_SECRET = os.environ.get('JWT_SECRET', 'change_me_in_prod')
JWT_ALGORITHM = os.environ.get('JWT_ALGORITHM', 'HS256')
JWT_EXPIRE_HOURS = int(os.environ.get('JWT_EXPIRE_HOURS', '168'))
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@magicai.test').lower()

IS_BETA = ENV == 'BETA'
IS_PROD = ENV == 'PROD'
IS_DEV = ENV == 'DEV'

EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')
MAGIC_HOUR_API_KEY = os.environ.get('MAGIC_HOUR_API_KEY', '')
