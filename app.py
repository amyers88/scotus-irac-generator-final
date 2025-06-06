import os
import logging
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import openai
import PyPDF2

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='.', static_url_path='')
# Configure CORS to allow all origins and headers for testing
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Configuration for file uploads
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_EXTENSIONS'] = ['.pdf']
app.config['UPLOAD_PATH'] = 'uploads'  # Create this directory if it doesn't exist

# Get OpenAI API key from environment variable
openai_api_key = os.environ.get('OPENAI_API_KEY')
if not openai_api_key:
    raise ValueError("No OPENAI_API_KEY environment variable set. Please set it in your Render environment variables.")

# Initialize OpenAI client
openai.api_key = openai_api_key

def extract_text_from_pdf(pdf_file):
    reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text

@app.route('/api/generate_irac', methods=['POST'])
def log_request_details():
    """Simple request logging that won't break the app"""
    try:
        logger.info(f"Request: {request.method} {request.path}")
    except:
        pass
    """Log details about the incoming request."""
    logger.info(f"Incoming request: {request.method} {request.path}")
    logger.info(f"Headers: {dict(request.headers)}")
    logger.info(f"Form data: {request.form}")
    logger.info(f"Files: {list(request.files.keys()) if request.files else 'No files'}")

def log_response(response):
    """Log details about the outgoing response."""
    logger.info(f"Outgoing response: {response.status}")
    return response

@app.before_request
def before_request():
    request.start_time = datetime.now()
    try:
        logger.info(f"Request: {request.method} {request.path}")
    except:
        pass
    return None
def before_request():
    request.start_time = datetime.now()
    log_request()

@app.after_request
def after_request(response):
    duration = (datetime.now() - request.start_time).total_seconds()
    logger.info(f"Request took {duration:.2f} seconds")
    return log_response(response)

@app.route('/api/generate_irac', methods=['POST'])
def generate_irac():
    try:
        # Log request data for debugging
        logger.info("Received request with form data: %s", request.form)
        logger.info("Received files: %s", request.files)
        
        role = request.form.get('role', 'student')
        case_name = request.form.get('caseName', '')
        docket_number = request.form.get('docketNumber', '')
        
        if 'pdf' not in request.files:
            error_msg = "No file part in the request"
            logger.error(error_msg)
            return jsonify({'error': error_msg}), 400
            
        pdf = request.files['pdf']
        
        if pdf.filename == '':
            error_msg = "No selected file"
            logger.error(error_msg)
            return jsonify({'error': error_msg}), 400
            
        if not pdf.filename.lower().endswith('.pdf'):
            error_msg = f"File must be a PDF, got {pdf.filename}"
            logger.error(error_msg)
            return jsonify({'error': error_msg}), 400
            
        logger.info(f"Processing file: {pdf.filename}")
        try:
            case_text = extract_text_from_pdf(pdf)
            if not case_text.strip():
                error_msg = "Failed to extract text from PDF. The file might be corrupted or scanned as an image."
                logger.error(error_msg)
                return jsonify({'error': error_msg}), 400
        except Exception as e:
            error_msg = f"Error processing PDF: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return jsonify({'error': error_msg}), 400
    
        # Add docket number to the case name if provided
        if docket_number:
            case_name = f"{case_name} (Docket No. {docket_number})" if case_name else f"Docket No. {docket_number}"

        if role == 'student':
            prompt = f"""You are a law professor creating study materials for your students. Read the following Supreme Court case and generate a comprehensive IRAC (Issue, Rule, Application, Conclusion) analysis with these sections:

### CASE CITATION
- Full case name and citation
- Court term and decision date

### VOTING ALIGNMENT
- Vote: [e.g., 6-3, 9-0, 5-4] - Must include the actual vote count
- Majority by: [Justice Name] - Specify the justice who wrote the majority opinion
- Joined by: [List all Justices in the majority] - Include all justices who joined
- Dissenting: [List all dissenting Justices] - Include 'None' if unanimous
- Concurring: [List any concurring Justices with their reasoning] - Include 'None' if none

### KEY FACTS
- 3-5 most important facts that influenced the Court's decision
- Focus on legally significant facts

### PROCEDURAL HISTORY
- Lower court decisions
- How the case reached this court

### ISSUE
- The precise legal question before the Court
- Frame it as a yes/no or either/or question

### RULE
- The legal principle(s) the Court applies
- Relevant precedent and its evolution
- Any competing legal standards

### ANALYSIS/APPLICATION
- Court's reasoning and legal analysis
- Application of law to facts
- Key policy considerations
- Competing views (concurrences/dissents if present)

### HOLDING
- The Court's specific decision
- Vote count and author of the opinion
- Any notable concurrences or dissents

### SIGNIFICANCE
• **Broader legal doctrine**: How this case fits into the larger legal framework
• **Future impact**: Potential implications for future cases and legal arguments
• **Educational value**: Why this case is significant in legal education
• **Policy considerations**: Any policy implications of the Court's decision

### PRECEDENTIAL VALUE
• **Controls current case?**: [Yes/No - Explain why this is or isn't the controlling precedent for the legal issue]
• **Distinguishable because:** [Explain specific factual or legal differences that would make this case inapplicable to other situations, or state 'Not applicable' if broadly applicable]
• **Potentially overruled by:** [List any subsequent cases that have directly criticized, limited, or overruled this decision, or 'None' if still good law]
• **Key case for:** [List 2-3 specific legal principles or doctrines this case is most frequently cited for, with brief explanations]
• **Jurisdictional reach:** [Specify if this is binding only in certain circuits or has nationwide application]

Case Text:
{case_text[:4000]}

Format the response in clear, well-structured markdown with bold section headers. Use headings, subheadings, and bullet points for readability. Include relevant case law citations where appropriate."""
        else:  # paralegal
            prompt = f"""You are a senior paralegal preparing a case brief for an attorney. For the case Trump v. United States (2024), ensure you provide complete and accurate information in all sections. If information is not available in the provided text, indicate 'Not specified in provided text'. Create a concise, practical IRAC summary with these sections:

### CASE CITATION
- Case name and citation
- Court and decision date

### VOTING ALIGNMENT
- Vote: [e.g., 6-3, 9-0, 5-4] - Must include the actual vote count
- Majority by: [Justice Name] - Specify the justice who wrote the majority opinion
- Joined by: [List all Justices in the majority] - Include all justices who joined
- Dissenting: [List all dissenting Justices] - Include 'None' if unanimous
- Concurring: [List any concurring Justices with their reasoning] - Include 'None' if none

### CASE STATUS
- [ ] Binding precedent (check if applicable)
- [ ] Persuasive authority (check if applicable)
- [ ] Overruled/Narrowed by: [List any cases that have overruled or narrowed this decision, or 'None' if still good law]
- [ ] Impact on existing precedent: [Describe how this affects previous rulings]

### KEY HOLDING
- The Court's main decision in 1-2 sentences
- The specific legal rule established

### PRECEDENTIAL VALUE
• **Controls current case?**: [Yes/No - Explain why this is or isn't the controlling precedent for the legal issue]
• **Distinguishable because:** [Explain specific factual or legal differences that would make this case inapplicable to other situations, or state 'Not applicable' if broadly applicable]
• **Potentially overruled by:** [List any subsequent cases that have directly criticized, limited, or overruled this decision, or 'None' if still good law]
• **Key case for:** [List 2-3 specific legal principles or doctrines this case is most frequently cited for, with brief explanations]
• **Jurisdictional reach:** [Specify if this is binding only in certain circuits or has nationwide application]

### PRACTICAL APPLICATION
• How to use this case in arguments
• When to cite it
• How it affects current law

### RELATED AUTHORITY
• **Key statutes:** [List relevant statutes and code sections]
• **Supporting cases:** [List and briefly describe cases that support this decision]
• **Contrary cases:** [List and briefly describe cases that might conflict with this decision]
• **Secondary sources:** [List relevant law review articles, treatises, or other commentary]

### PRACTICE TIPS
• **Best uses in litigation:** [Describe the most effective ways to use this case in legal arguments]
• **Potential weaknesses:** [Note any limitations or weaknesses in the Court's reasoning]
• **Distinguishing factors:** [Explain how to distinguish this case from unfavorable precedent]
• **Drafting guidance:** [Tips for citing this case in briefs and motions]

Case Text:
{case_text[:4000]}

Keep it under 500 words. Use bullet points and clear headers. Focus on practical implications and how to use this case in practice. Include checkboxes for quick reference. Highlight any language that would be persuasive in a brief or motion."""

        try:
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=700,
                temperature=0.3
            )
            irac_summary = response.choices[0].message.content.strip()
            return jsonify({'summary': irac_summary})
        except Exception as e:
            print(f"Error generating IRAC: {str(e)}")
            return jsonify({'error': f'Error generating IRAC: {str(e)}'}), 500
            
    except Exception as e:
        print(f"Error processing request: {str(e)}")
        return jsonify({'error': f'Error processing request: {str(e)}'}), 500

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    if os.path.exists(path):
        return send_from_directory('.', path)
    return 'Not Found', 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5010))
    app.run(host='0.0.0.0', port=port)
