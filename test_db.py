from app.db.database import engine

try:
    with engine.connect() as conn:
        print("✅ Connected to Supabase DB successfully")
except Exception as e:
    print("❌ DB connection failed")
    print(e)
