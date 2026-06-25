from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

SQLALCHEMY_DATABASE_URL = "sqlite:///./data/metadata_bot.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    make = Column(String, default="Apple")
    model = Column(String, default="iPhone 15 Pro Max")
    software = Column(String, default="17.5.1")
    lens_make = Column(String, default="Apple")
    lens_model = Column(String, default="iPhone 15 Pro Max back triple camera 6.765mm f/1.78")
    f_number = Column(Float, default=1.78)
    focal_length = Column(Float, default=6.765)
    iso = Column(Integer, default=50)
    exposure_time = Column(String, default="1/2000")
    gps_latitude = Column(Float, default=25.7617)
    gps_longitude = Column(Float, default=-80.1918)
    gps_altitude = Column(Float, default=5.0)
    location_name = Column(String, default="Miami, FL")
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ProcessedFile(Base):
    __tablename__ = "processed_files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    original_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


def create_tables():
    import os
    os.makedirs("data", exist_ok=True)
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
