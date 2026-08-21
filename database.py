from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, Boolean
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

SQLALCHEMY_DATABASE_URL = "sqlite:///./nano_data.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={
                       "check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class SimulationRecord(Base):
    __tablename__ = "simulation_records"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    project_name = Column(String, default="Untitled Project")
    contaminant_type = Column(String)
    initial_concentration = Column(Float)
    nano_material = Column(String)
    nano_dosage = Column(Float)
    uv_intensity = Column(Float)
    biomass_density = Column(Float)
    contact_time = Column(Float)
    ph = Column(Float)

    # Results
    effluent_concentration = Column(Float)
    total_removal_efficiency = Column(Float)
    nano_phase_efficiency = Column(Float)
    bio_phase_efficiency = Column(Float)
    bio_viability = Column(Float)
    nano_leaching = Column(Float)

    # Compliance & Optimization Data (Added to fix TypeError)
    epa_mcl = Column(Float, nullable=True)
    is_compliant = Column(Boolean, nullable=True)
    min_required_dosage = Column(Float, nullable=True)
    required_contact_time = Column(Float, nullable=True)


Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()