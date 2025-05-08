import pandas as pd
import os
from sqlalchemy.exc import SQLAlchemyError
from models import Patient, Base, engine, SessionLocal
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def reset_database():
    """Drop and recreate the database tables."""
    try:
        logger.info("Resetting database")
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        logger.info("Database reset successfully")
    except SQLAlchemyError as e:
        logger.error("Error resetting database: %s", str(e))
        raise

def load_data_from_csv(csv_path, row_limit=10000):
    """Load data from CSV into the patients table, up to row_limit rows."""
    if not os.path.exists(csv_path):
        logger.error("CSV file not found at: %s", csv_path)
        raise FileNotFoundError(f"CSV file not found at: {csv_path}")

    try:
        logger.info("Loading CSV file: %s", csv_path)
        # Read only the first row_limit rows
        df = pd.read_csv(csv_path, nrows=row_limit)
        logger.info("Read %d rows from CSV", len(df))

        # Define expected columns based on Patient model
        expected_columns = [
            'PatientID', 'Name', 'Sex', 'State', 'GeneralHealth',
            'HasChronicCondition', 'HospitalStayDuration', 'RiskCategory',
            'DoctorName', 'Allergies', 'ChiefComplaint', 'AdmissionDate',
            'DischargeDate', 'TestReports'
        ]

        # Check for missing columns and add defaults
        for col in expected_columns:
            if col not in df.columns:
                logger.warning("Column %s missing in CSV, adding with default value", col)
                df[col] = None if col != 'TestReports' else ''

        # Select only expected columns
        df = df[expected_columns]

        # Clean and validate data
        df['PatientID'] = pd.to_numeric(df['PatientID'], errors='coerce').fillna(0).astype(int)
        df['HasChronicCondition'] = df['HasChronicCondition'].map({True: True, False: False, 'Yes': True, 'No': False, 1: True, 0: False}).fillna(False)
        df['HospitalStayDuration'] = pd.to_numeric(df['HospitalStayDuration'], errors='coerce').fillna(1).astype(int)
        df['Name'] = df['Name'].fillna('Unknown').astype(str)
        df['Sex'] = df['Sex'].fillna('Unknown').astype(str)
        df['State'] = df['State'].fillna('Unknown').astype(str)
        df['GeneralHealth'] = df['GeneralHealth'].fillna('Unknown').astype(str)
        df['RiskCategory'] = df['RiskCategory'].fillna('Unknown').astype(str)
        df['DoctorName'] = df['DoctorName'].fillna('Dr. Anita Sharma').astype(str)
        df['Allergies'] = df['Allergies'].fillna('None').astype(str)
        df['ChiefComplaint'] = df['ChiefComplaint'].fillna('Unknown').astype(str)
        df['AdmissionDate'] = df['AdmissionDate'].fillna('Unknown').astype(str)
        df['DischargeDate'] = df['DischargeDate'].fillna('Unknown').astype(str)
        df['TestReports'] = df['TestReports'].fillna('').astype(str)

        session = SessionLocal()
        try:
            # Insert data in chunks to avoid memory issues
            chunk_size = 1000
            for start in range(0, len(df), chunk_size):
                chunk = df[start:start + chunk_size]
                patients = [
                    Patient(
                        PatientID=row['PatientID'],
                        Name=row['Name'],
                        Sex=row['Sex'],
                        State=row['State'],
                        GeneralHealth=row['GeneralHealth'],
                        HasChronicCondition=row['HasChronicCondition'],
                        HospitalStayDuration=row['HospitalStayDuration'],
                        RiskCategory=row['RiskCategory'],
                        DoctorName=row['DoctorName'],
                        Allergies=row['Allergies'],
                        ChiefComplaint=row['ChiefComplaint'],
                        AdmissionDate=row['AdmissionDate'],
                        DischargeDate=row['DischargeDate'],
                        TestReports=row['TestReports']
                    ) for _, row in chunk.iterrows() if row['PatientID'] > 0
                ]
                session.bulk_save_objects(patients)
                session.commit()
                logger.info("Inserted %d-%d of %d rows", start, min(start + chunk_size, len(df)), len(df))
        except SQLAlchemyError as e:
            session.rollback()
            logger.error("Error inserting data into database: %s", str(e))
            raise
        finally:
            session.close()
        logger.info("Successfully loaded %d rows into database", len(df))
    except pd.errors.EmptyDataError:
        logger.error("CSV file is empty: %s", csv_path)
        raise
    except Exception as e:
        logger.error("Unexpected error loading CSV: %s", str(e))
        raise

if __name__ == "__main__":
    csv_path = os.path.join(os.path.dirname(__file__), "dataset.csv")
    reset_database()
    load_data_from_csv(csv_path, row_limit=10000)