from flask import Flask, render_template, request, jsonify, send_file
from models import Patient, SessionLocal
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from fpdf import FPDF
import logging
import os
import tempfile
from sqlalchemy import func
from werkzeug.utils import secure_filename

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# File upload configuration
UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB limit

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Load AI model with retry mechanism
def load_ai_model():
    try:
        from transformers import pipeline
        summarizer = pipeline("text-generation", model="distilgpt2")
        logger.info("AI model loaded successfully")
        return summarizer
    except Exception as e:
        logger.error("Error loading AI model: %s, using fallback summary", str(e))
        return None

summarizer = load_ai_model()

# Map GeneralHealth to diseases and age
def map_disease_and_age(general_health, has_chronic, risk_category):
    age_map = {
        'Obese': 'Adult (40-60)',
        'Overweight': 'Adult (30-50)',
        'Normal': 'Young Adult (20-40)'
    }
    age = age_map.get(risk_category, 'Adult (30-60)')
    
    if has_chronic:
        if general_health == 'Fair':
            return 'Hypertension', 'High blood pressure', age
        elif general_health == 'Poor':
            return 'Diabetes', 'High blood sugar', age
        else:
            return 'Chronic Heart Disease', 'Chest pain', age
    else:
        return 'Acute Respiratory Infection', 'Shortness of breath', age

# Function to fetch patient data by ID
def get_patient_data(patient_id):
    session = SessionLocal()
    try:
        patient_id_int = int(patient_id)
        logger.debug("Looking up PatientID: %d", patient_id_int)
        patient = session.query(Patient).filter(Patient.PatientID == patient_id_int).first()
        if patient:
            logger.debug("Patient found for ID: %d", patient_id_int)
            return {
                'PatientID': patient.PatientID,
                'Name': patient.Name,
                'Sex': patient.Sex,
                'State': patient.State,
                'GeneralHealth': patient.GeneralHealth,
                'HasChronicCondition': patient.HasChronicCondition,
                'HospitalStayDuration': patient.HospitalStayDuration,
                'RiskCategory': patient.RiskCategory,
                'DoctorName': patient.DoctorName,
                'Allergies': patient.Allergies,
                'ChiefComplaint': patient.ChiefComplaint,
                'AdmissionDate': patient.AdmissionDate,
                'DischargeDate': patient.DischargeDate,
                'TestReports': patient.TestReports
            }
        logger.warning("No patient found for ID: %d", patient_id_int)
        return None
    except ValueError as ve:
        logger.error("Invalid Patient ID format: %s, error: %s", patient_id, str(ve))
        return None
    except Exception as e:
        logger.error("Error fetching patient data for ID %s: %s", patient_id, str(e))
        return None
    finally:
        session.close()

# Function to get all patient IDs
def get_patient_ids():
    session = SessionLocal()
    try:
        patient_ids = set(str(pid[0]) for pid in session.query(Patient.PatientID).all())
        logger.debug("Fetched %d patient IDs from database", len(patient_ids))
        return patient_ids
    except Exception as e:
        logger.error("Error fetching patient IDs: %s", str(e))
        return set()
    finally:
        session.close()

# Function to generate AI-enhanced summary
def generate_summary(patient_data, detail_level, doctor_notes, discharge_date):
    try:
        name = patient_data.get('Name', 'Unknown')
        sex = patient_data.get('Sex', 'Unknown')
        state = patient_data.get('State', 'Unknown')
        general_health = patient_data.get('GeneralHealth', 'Unknown')
        has_chronic = patient_data.get('HasChronicCondition', False)
        stay_duration = patient_data.get('HospitalStayDuration', 'Unknown')
        risk_category = patient_data.get('RiskCategory', 'Unknown')
        doctor_name = patient_data.get('DoctorName', 'Dr. Anita Sharma')
        allergies = patient_data.get('Allergies', 'None')
        chief_complaint = patient_data.get('ChiefComplaint', 'Unknown')
        admission_date = patient_data.get('AdmissionDate', (datetime.strptime(discharge_date, '%Y-%m-%d') - timedelta(days=int(stay_duration or 1))).strftime('%Y-%m-%d'))
        disease, complaint_default, age = map_disease_and_age(general_health, has_chronic, risk_category)
        
        # Template for base summary
        hpi = f"Presented with {chief_complaint or complaint_default} for {'1 week' if has_chronic else '3 days'}."
        past_history = f"History of {'obesity' if risk_category == 'Obese' else 'no major conditions'}."
        social_history = f"{'Non-smoker, sedentary' if risk_category == 'Obese' else 'Non-smoker, active'} lifestyle."
        physical_exam = f"{'BP 140/90' if disease == 'Hypertension' else 'Blood glucose 180 mg/dL' if disease == 'Diabetes' else 'HR 80 bpm'} on admission."
        lab_data = f"{'HbA1c 7.0%' if disease == 'Diabetes' else 'Normal lipids' if disease == 'Chronic Heart Disease' else 'CRP elevated' if disease == 'Acute Respiratory Infection' else 'Normal labs'}."
        hospital_course = f"{'Monitored BP and adjusted medications' if disease == 'Hypertension' else 'Managed glucose levels' if disease == 'Diabetes' else 'Cardiac monitoring' if disease == 'Chronic Heart Disease' else 'Antibiotic therapy'}."
        
        medications_dict = {
            'Hypertension': 'Lisinopril 10mg daily for 30 days',
            'Diabetes': 'Metformin 500mg twice daily for 60 days',
            'Chronic Heart Disease': 'Aspirin 81mg daily, Atorvastatin 20mg daily for 90 days',
            'Acute Respiratory Infection': 'Amoxicillin 500mg three times daily for 7 days'
        }
        medications = medications_dict.get(disease, 'Standard medications prescribed')
        
        diet = f"{'Low-salt diet' if disease == 'Hypertension' else 'Low-sugar diet' if disease == 'Diabetes' else 'Heart-healthy diet' if disease == 'Chronic Heart Disease' else 'Balanced diet'}."
        activity = f"{'Light walking 30 min daily' if has_chronic else 'Resume normal activity in 1 week'}."
        follow_up = f"Follow up in {'1 month' if has_chronic else '2 weeks'} with {'blood pressure check' if disease == 'Hypertension' else 'blood sugar test' if disease == 'Diabetes' else 'cardiac evaluation' if disease == 'Chronic Heart Disease' else 'respiratory check'}."
        discharge_instructions = f"{'Monitor BP daily' if disease == 'Hypertension' else 'Check glucose regularly' if disease == 'Diabetes' else 'Report chest pain immediately' if disease == 'Chronic Heart Disease' else 'Complete antibiotic course'}."
        
        condition = 'Stable' if general_health in ['Good', 'Very good', 'Excellent'] else 'Improved' if general_health == 'Fair' else 'Unchanged'
        
        # Simplified AI-generated notes with robust fallback
        ai_notes = ""
        if summarizer:
            prompt = f"Generate a concise medical note for a patient with {disease}. Describe the disease briefly, mention key patient data (Health: {general_health}, Risk: {risk_category}, Stay: {stay_duration} days), and suggest one treatment or lifestyle change. Keep it under 150 words."
            try:
                logger.debug("Generating AI notes with prompt: %s", prompt)
                ai_output = summarizer(prompt, max_length=300, num_return_sequences=1, truncation=True, temperature=0.8, do_sample=True, min_length=50)[0]['generated_text']
                ai_output = ai_output.replace(prompt, '').strip()
                logger.debug("Raw AI output: %s", ai_output)
                if not ai_output or len(ai_output) < 20:
                    raise ValueError("AI output is empty or too short")
                ai_notes = ai_output[:200].strip()
                ai_notes = f"AI Notes: {ai_notes}"
                ai_notes = ai_notes.replace('\n', ' ')
                logger.info("AI notes generated successfully: %s", ai_notes)
            except Exception as e:
                logger.error("Error generating AI notes: %s, using fallback", str(e))
                ai_notes = f"AI Notes: {disease} requires ongoing monitoring. {'Manage BP with low-salt diet' if disease == 'Hypertension' else 'Control glucose with diet' if disease == 'Diabetes' else 'Monitor heart health' if disease == 'Chronic Heart Disease' else 'Complete antibiotics'}. [AI generation failed; using fallback]"
        else:
            logger.warning("AI model unavailable, using fallback notes")
            ai_notes = f"AI Notes: {disease} requires ongoing monitoring. {'Manage BP with low-salt diet' if disease == 'Hypertension' else 'Control glucose with diet' if disease == 'Diabetes' else 'Monitor heart health' if disease == 'Chronic Heart Disease' else 'Complete antibiotics'}. [AI model unavailable]"

        patient_ids = get_patient_ids()
        return {
            'hpi': hpi,
            'past_history': past_history,
            'social_history': social_history,
            'physical_exam': physical_exam,
            'lab_data': lab_data,
            'hospital_course': hospital_course,
            'medications': medications,
            'diet': diet,
            'activity': activity,
            'follow_up': follow_up,
            'discharge_instructions': discharge_instructions,
            'discharge_date': discharge_date,
            'admission_date': admission_date,
            'condition': condition,
            'allergies': allergies,
            'chief_complaint': chief_complaint or complaint_default,
            'diagnosis': f"{disease}. Secondary: {'Obesity-related complications' if risk_category == 'Obese' else 'None'}.",
            'doctor_name': doctor_name,
            'age': age,
            'is_fallback': str(patient_data.get('PatientID', 'Unknown')) not in patient_ids,
            'ai_notes': ai_notes
        }
    except Exception as e:
        logger.error("Error in generate_summary: %s", str(e))
        raise ValueError(f"Failed to generate summary: {str(e)}")

# Function to generate visually enhanced PDF
def generate_pdf(patient_data, summary):
    try:
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_margins(20, 15, 20)

        # Draw border around content
        pdf.set_draw_color(0, 102, 204)  # Blue border
        pdf.rect(10, 10, 190, 277)  # A4 size: 210x297mm, 10mm margin

        # Hospital header with logo
        logo_path = os.path.join(os.path.dirname(__file__), "static", "images", "logo.png")
        try:
            pdf.image(logo_path, x=85, y=15, w=40)  # Centered logo
        except Exception as e:
            logger.warning("Logo image not found or invalid at %s: %s", logo_path, str(e))

        pdf.set_y(55)
        pdf.set_fill_color(0, 102, 204)  # Blue header
        pdf.set_text_color(255, 255, 255)  # White text
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, "ICareForYou", ln=True, align='C', fill=True)
        pdf.set_font("Arial", 'I', 10)
        pdf.set_text_color(0, 0, 0)  # Black text
        pdf.cell(0, 8, "Hyderabad, Telangana, India | Mobile: +91 9123696969", ln=True, align='C')
        pdf.ln(10)

        # Horizontal line separator
        pdf.set_draw_color(0, 102, 204)
        pdf.line(20, pdf.get_y(), 190, pdf.get_y())
        pdf.ln(5)

        # Identifying data
        pdf.set_font("Arial", 'B', 12)
        pdf.set_fill_color(240, 240, 240)  # Light gray
        pdf.cell(0, 10, "Identifying Data:", ln=True, fill=True)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, f"Patient: {patient_data.get('Name', 'Unknown')}", align='L')
        pdf.multi_cell(0, 10, f"Medical Record Number: {patient_data.get('PatientID', 'Unknown')}", align='L')
        pdf.multi_cell(0, 10, f"Age: {summary['age']}", align='L')
        pdf.multi_cell(0, 10, f"Sex: {patient_data.get('Sex', 'Unknown')}", align='L')
        pdf.multi_cell(0, 10, f"Admission Date: {summary['admission_date']}", align='L')
        pdf.multi_cell(0, 10, f"Discharge Date: {summary['discharge_date']}", align='L')
        if summary['is_fallback']:
            pdf.multi_cell(0, 10, "Note: Generated based on similar patient data", align='L')
        pdf.ln(5)

        # Service
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Service:", ln=True, fill=True)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, "General Medicine")
        pdf.ln(5)

        # Chief complaint
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Chief Complaint:", ln=True, fill=True)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, summary['chief_complaint'])
        pdf.ln(5)

        # HPI
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "History of Present Illness:", ln=True, fill=True)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, summary['hpi'])
        pdf.ln(5)

        # Past history
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Past Medical/Surgical History:", ln=True, fill=True)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, summary['past_history'])
        pdf.ln(5)

        # Social history
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Social History:", ln=True, fill=True)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, summary['social_history'])
        pdf.ln(5)

        # Allergies
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Allergies:", ln=True, fill=True)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, summary['allergies'])
        pdf.ln(5)

        # Physical exam
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Physical Exam on Admission:", ln=True, fill=True)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, summary['physical_exam'])
        pdf.ln(5)

        # Lab data
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Laboratory Data:", ln=True, fill=True)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, summary['lab_data'])
        pdf.ln(5)

        # Hospital course
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Hospital Course:", ln=True, fill=True)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, summary['hospital_course'])
        pdf.ln(5)

        # Condition at discharge
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Condition at Discharge:", ln=True, fill=True)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, summary['condition'])
        pdf.ln(5)

        # Discharge diagnoses
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Discharge Diagnoses:", ln=True, fill=True)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, summary['diagnosis'])
        pdf.ln(5)

        # Discharge medications
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Discharge Medications:", ln=True, fill=True)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, summary['medications'])
        pdf.ln(5)

        # Diet
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Diet:", ln=True, fill=True)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, summary['diet'])
        pdf.ln(5)

        # Activity
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Activity:", ln=True, fill=True)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, summary['activity'])
        pdf.ln(5)

        # Follow-up
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Follow-Up:", ln=True, fill=True)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, summary['follow_up'])
        pdf.ln(5)

        # Discharge instructions
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Discharge Instructions:", ln=True, fill=True)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, summary['discharge_instructions'])
        pdf.ln(5)

        # AI notes
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "AI-Generated Notes:", ln=True, fill=True)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, summary['ai_notes'])
        pdf.ln(5)

        # Signature
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, f"Signature: {summary['doctor_name']}", ln=True, fill=True)
        pdf.set_font("Arial", 'I', 12)
        pdf.cell(0, 10, "Consultant Physician, ICareForYou", ln=True)
        pdf.ln(10)

        # Horizontal line separator
        pdf.set_draw_color(0, 102, 204)
        pdf.line(20, pdf.get_y(), 190, pdf.get_y())
        pdf.ln(5)

        # Hospital footer
        pdf.set_fill_color(0, 102, 204)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, "ICareForYou", ln=True, align='C', fill=True)
        pdf.set_font("Arial", 'I', 10)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 8, "Hyderabad, Telangana, India | Mobile: +91 9123696969", ln=True, align='C')

        # Use /tmp for PDF storage
        pdf_file = os.path.join(tempfile.gettempdir(), "discharge_summary.pdf")
        pdf.output(pdf_file)
        logger.info("PDF created")
        return pdf_file
    except Exception as e:
        logger.error("Error in generate_pdf: %s", str(e))
        raise ValueError(f"Failed to generate PDF: {str(e)}")

@app.route('/')
def index():
    logger.info("Serving index")
    return render_template('index.html')

@app.route('/add_patient')
def add_patient():
    logger.info("Serving add patient page")
    return render_template('add_patient.html')

@app.route('/view_database')
def view_database():
    logger.info("Serving view database page")
    session = SessionLocal()
    try:
        page = int(request.args.get('page', 1))
        per_page = 100
        offset = (page - 1) * per_page
        patients = session.query(Patient).order_by(Patient.PatientID.desc()).offset(offset).limit(per_page).all()
        total_patients = session.query(Patient).count()
        has_more = offset + len(patients) < total_patients
        logger.info("Fetched %d patients for view_database, page %d, has_more: %s", len(patients), page, has_more)
        return jsonify({
            'patients': [{
                'PatientID': p.PatientID,
                'Name': p.Name,
                'Sex': p.Sex,
                'State': p.State,
                'GeneralHealth': p.GeneralHealth,
                'HasChronicCondition': p.HasChronicCondition,
                'HospitalStayDuration': p.HospitalStayDuration,
                'RiskCategory': p.RiskCategory,
                'DoctorName': p.DoctorName,
                'Allergies': p.Allergies,
                'ChiefComplaint': p.ChiefComplaint,
                'AdmissionDate': p.AdmissionDate,
                'DischargeDate': p.DischargeDate,
                'TestReports': p.TestReports
            } for p in patients],
            'has_more': has_more,
            'next_page': page + 1
        }) if request.args.get('ajax') else render_template('view_database.html', patients=patients, has_more=has_more, next_page=page + 1)
    except Exception as e:
        logger.error("Error fetching patients for view_database: %s", str(e))
        return jsonify({'error': 'Failed to load patient database'}), 500
    finally:
        session.close()

@app.route('/preview', methods=['POST'])
def preview():
    patient_id = request.form.get('patient_id')
    try:
        patient_id_int = int(patient_id)
        patient_id_str = str(patient_id_int)
    except (ValueError, TypeError):
        logger.error("Invalid Patient ID format: %s", patient_id)
        return jsonify({'error': '⚠️ Invalid Patient ID. Please enter a valid number.'}), 400

    patient_data = get_patient_data(patient_id)
    if patient_data:
        disease, complaint, age = map_disease_and_age(
            patient_data.get('GeneralHealth', 'Unknown'),
            patient_data.get('HasChronicCondition', False),
            patient_data.get('RiskCategory', 'Unknown')
        )
        patient_ids = get_patient_ids()
        return jsonify({
            'name': patient_data.get('Name', 'Unknown'),
            'sex': patient_data.get('Sex', 'Unknown'),
            'age': age,
            'state': patient_data.get('State', 'Unknown'),
            'disease': disease,
            'chief_complaint': patient_data.get('ChiefComplaint', complaint),
            'stay_duration': patient_data.get('HospitalStayDuration', 'Unknown'),
            'chronic': patient_data.get('HasChronicCondition', False),
            'is_fallback': str(patient_data.get('PatientID', 'Unknown')) not in patient_ids,
            'doctor_name': patient_data.get('DoctorName', 'Dr. Anita Sharma'),
            'allergies': patient_data.get('Allergies', 'None'),
            'admission_date': patient_data.get('AdmissionDate', 'Unknown'),
            'discharge_date': patient_data.get('DischargeDate', 'Unknown'),
            'test_reports': patient_data.get('TestReports', '')
        })
    logger.error("No patient data available for ID: %s", patient_id)
    return jsonify({'error': f'⚠️ No patient found with ID {patient_id}. Please check the ID or add the patient.'}), 404

@app.route('/generate', methods=['POST'])
def generate():
    logger.info("Received generate request")
    patient_id = request.form.get('patient_id')
    detail_level = request.form.get('detail_level')
    doctor_notes = request.form.get('doctor_notes', '')
    discharge_date = request.form.get('discharge_date', datetime.now().strftime('%Y-%m-%d'))

    try:
        patient_id_int = int(patient_id)
        patient_id_str = str(patient_id_int)
    except (ValueError, TypeError):
        logger.error("Invalid patient ID format: %s", patient_id)
        return jsonify({'error': '⚠️ Invalid Patient ID. Please enter a valid number.'}), 400

    patient_data = get_patient_data(patient_id)
    if not patient_data:
        logger.error("No patient data available for ID: %s", patient_id)
        return jsonify({'error': f'⚠️ No patient found with ID {patient_id}. Please check the ID or add the patient.'}), 404

    try:
        logger.info("Generating summary with AI for patient ID: %s", patient_id)
        summary = generate_summary(patient_data, detail_level, doctor_notes, discharge_date)
        logger.info("Summary generated, creating PDF")
        pdf_file = generate_pdf(patient_data, summary)
        logger.info("PDF created at: %s", pdf_file)
        return jsonify({'summary': summary, 'pdf_file': 'discharge_summary.pdf'})
    except ValueError as ve:
        logger.error("ValueError in processing: %s", str(ve))
        return jsonify({'error': str(ve)}), 500
    except Exception as e:
        logger.error("Unexpected error in processing: %s", str(e))
        return jsonify({'error': f'Failed to generate summary: {str(e)}'}), 500

@app.route('/download/<filename>')
def download(filename):
    logger.info("Downloading %s", filename)
    try:
        file_path = os.path.join(tempfile.gettempdir(), filename)
        if not os.path.exists(file_path):
            logger.error("File not found: %s", file_path)
            return jsonify({'error': 'File not found'}), 404
        return send_file(file_path, as_attachment=True, download_name='discharge_summary.pdf')
    except Exception as e:
        logger.error("Error downloading file %s: %s", filename, str(e))
        return jsonify({'error': 'File not found'}), 404

@app.route('/uploads/<filename>')
def serve_uploaded_file(filename):
    logger.info("Serving uploaded file: %s", filename)
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if not os.path.exists(file_path):
            logger.error("File not found: %s", file_path)
            return jsonify({'error': 'File not found'}), 404
        return send_file(file_path)
    except Exception as e:
        logger.error("Error serving file %s: %s", filename, str(e))
        return jsonify({'error': 'File not found'}), 404

@app.route('/add_patient', methods=['POST'])
def add_patient_post():
    logger.info("Received add patient request")
    session = SessionLocal()
    try:
        # Get next PatientID
        max_id = session.query(func.max(Patient.PatientID)).scalar() or 0
        next_id = max_id + 1

        # Handle file upload
        test_report_path = ''
        if 'test_report' in request.files:
            file = request.files['test_report']
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{next_id}_{file.filename}")
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                test_report_path = f"uploads/{filename}"
                logger.info("Test report uploaded: %s", test_report_path)
            else:
                logger.warning("Invalid or no test report uploaded")

        # Get form data
        new_patient = Patient(
            PatientID=next_id,
            Name=request.form.get('name', 'Unknown'),
            Sex=request.form.get('sex', 'Unknown'),
            State=request.form.get('state', 'Unknown'),
            GeneralHealth=request.form.get('general_health', 'Unknown'),
            HasChronicCondition=request.form.get('chronic_condition') == 'Yes',
            HospitalStayDuration=int(request.form.get('stay_duration', 1)),
            RiskCategory=request.form.get('risk_category', 'Unknown'),
            DoctorName=request.form.get('doctor_name', 'Dr. Anita Sharma'),
            Allergies=request.form.get('allergies', 'None'),
            AdmissionDate=request.form.get('admission_date', 'Unknown'),
            DischargeDate=request.form.get('discharge_date', 'Unknown'),
            ChiefComplaint=request.form.get('chief_complaint', 'Unknown'),
            TestReports=test_report_path
        )

        # Add to database
        session.add(new_patient)
        session.commit()
        logger.info("Patient added with ID: %s", next_id)

        # Return success response with redirect
        return jsonify({
            'message': f"Patient added with ID {next_id}",
            'redirect': '/'
        })
    except Exception as e:
        session.rollback()
        logger.error("Error adding patient: %s", str(e))
        return jsonify({
            'error': f"Failed to add patient: {str(e)}"
        }), 500
    finally:
        session.close()

@app.route('/upload_test_report', methods=['POST'])
def upload_test_report():
    logger.info("Received test report upload request")
    session = SessionLocal()
    try:
        patient_id = request.form.get('patient_id')
        if not patient_id:
            return jsonify({'error': '⚠️ Patient ID is required'}), 400

        patient_id_int = int(patient_id)
        patient = session.query(Patient).filter(Patient.PatientID == patient_id_int).first()
        if not patient:
            return jsonify({'error': f'⚠️ No patient found with ID {patient_id}'}), 404

        if 'test_report' not in request.files:
            return jsonify({'error': '⚠️ No file uploaded'}), 400

        file = request.files['test_report']
        if file and allowed_file(file.filename):
            filename = secure_filename(f"{patient_id}_{file.filename}")
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            patient.TestReports = f"uploads/{filename}"
            session.commit()
            logger.info("Test report uploaded for PatientID %s: %s", patient_id, patient.TestReports)
            return jsonify({'message': f"Test report uploaded for Patient ID {patient_id}"})
        else:
            return jsonify({'error': '⚠️ Invalid file type. Only JPG, PNG, or PDF allowed.'}), 400
    except Exception as e:
        session.rollback()
        logger.error("Error uploading test report: %s", str(e))
        return jsonify({'error': f"Failed to upload test report: {str(e)}"}), 500
    finally:
        session.close()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)