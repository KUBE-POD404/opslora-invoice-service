from app.database import engine, Base
from app.models.invoice import Invoice

def create_tables():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    create_tables()