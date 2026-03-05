from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import openai

app = Flask(__name__)
CORS(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://your_db_url_here'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

openai.api_key = "your-openai-api-key"

# Lead Model
class Lead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    business_name = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(255), nullable=False)
    score = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default="New")
    last_interaction = db.Column(db.String(255), nullable=True)
    personalized_message = db.Column(db.String(255), nullable=True)

    def __repr__(self):
        return f"<Lead {self.business_name}>"

@app.route('/leads', methods=['POST'])
def create_lead():
    data = request.json
    new_lead = Lead(
        business_name=data['business_name'],
        url=data['url'],
        score=data['score'],
        status="New"
    )
    db.session.add(new_lead)
    db.session.commit()
    return jsonify({"message": "Lead created successfully!"}), 201

@app.route('/leads', methods=['GET'])
def get_all_leads():
    leads = Lead.query.all()
    return jsonify([{
        "business_name": lead.business_name,
        "url": lead.url,
        "score": lead.score,
        "status": lead.status,
        "last_interaction": lead.last_interaction
    } for lead in leads])

@app.route('/lead/<int:lead_id>', methods=['GET'])
def get_lead(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    return jsonify({
        "business_name": lead.business_name,
        "url": lead.url,
        "score": lead.score,
        "status": lead.status,
        "personalized_message": lead.personalized_message
    })

@app.route('/lead/<int:lead_id>', methods=['PUT'])
def update_lead(lead_id):
    data = request.json
    lead = Lead.query.get_or_404(lead_id)
    lead.status = data.get('status', lead.status)
    lead.last_interaction = data.get('last_interaction', lead.last_interaction)
    lead.personalized_message = generate_personalized_message(lead.url)
    db.session.commit()
    return jsonify({"message": "Lead updated successfully!"})

# Function to generate personalized message using OpenAI
def generate_personalized_message(url):
    response = openai.Completion.create(
        model="text-davinci-003",
        prompt=f"Generate a personalized message for a business based on the following URL: {url}",
        max_tokens=100
    )
    return response.choices[0].text.strip()

if __name__ == '__main__':
    app.run(debug=True)
