from sqlalchemy import create_engine, Column, Integer, String, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Database configuration
DATABASE_URL = "sqlite:///smartdischarge.db"
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Patient(Base):
    __tablename__ = "patients"

    PatientID = Column(Integer, primary_key=True)
    Name = Column(String, nullable=True)
    Sex = Column(String, nullable=True)
    State = Column(String, nullable=True)
    GeneralHealth = Column(String, nullable=True)
    HasChronicCondition = Column(Boolean, nullable=True)
    HospitalStayDuration = Column(Integer, nullable=True)
    RiskCategory = Column(String, nullable=True)
    DoctorName = Column(String, nullable=True)
    Allergies = Column(String, nullable=True)
    ChiefComplaint = Column(String, nullable=True)
    AdmissionDate = Column(String, nullable=True)
    DischargeDate = Column(String, nullable=True)
    TestReports = Column(String, nullable=True)

    # Index for faster lookups on PatientID
    __table_args__ = (Index('idx_patient_id', 'PatientID'),)

# Create tables
Base.metadata.create_all(engine)