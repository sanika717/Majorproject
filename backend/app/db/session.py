from urllib.parse import urlparse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
from backend.app.core.config import settings

db_url = settings.DATABASE_URL or ""

# Ensure psycopg2 driver if standard postgresql:// is provided and no driver specified
if db_url.startswith("postgresql://"):
    # SQLAlchemy 2.0 defaults postgresql:// to psycopg (v3). Use psycopg2 if installed and preferred
    db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
elif db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)

# Check port and parse URL
connect_args = {}
parsed = urlparse(db_url)
is_pooler = False

if parsed.port == 6543:
    is_pooler = True

# Enforce sslmode=require if connected to remote/hosted postgres (or supabase)
if parsed.hostname and parsed.hostname != "localhost" and parsed.hostname != "127.0.0.1":
    connect_args["sslmode"] = "require"

engine_kwargs = {
    "pool_pre_ping": True,
    "connect_args": connect_args,
}

if is_pooler:
    # Port 6543 is Supabase transaction pooler (PgBouncer); client side pooling should be disabled
    engine_kwargs["poolclass"] = NullPool
else:
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine = create_engine(db_url, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
