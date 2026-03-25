from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
from datetime import datetime, timedelta
import os
import uuid
from transformers import pipeline

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')
CORS(app)

# Initialize chatbot
print("Loading chatbot model...")
classifier = pipeline(
    "zero-shot-classification",
    model="typeform/distilbert-base-uncased-mnli",
    device=-1  # Use CPU
)

# Sample events database
events = [
    {"id": 1, "name": "AI & Machine Learning Workshop", "category": "technical", 
     "date": "May 15, 2024", "description": "Learn AI fundamentals", "capacity": 50, "registered": 30},
    {"id": 2, "name": "Annual Career Fair 2024", "category": "career", 
     "date": "May 20, 2024", "description": "Meet top employers", "capacity": 200, "registered": 150},
    {"id": 3, "name": "Spring Cultural Festival", "category": "cultural", 
     "date": "May 25, 2024", "description": "Celebrate diversity", "capacity": 500, "registered": 320},
    {"id": 4, "name": "Basketball Tournament", "category": "sports", 
     "date": "May 18, 2024", "description": "Inter-university competition", "capacity": 300, "registered": 180},
    {"id": 5, "name": "Research Symposium", "category": "academic", 
     "date": "May 22, 2024", "description": "Student research showcase", "capacity": 150, "registered": 95},
]

categories = ["technical", "career", "cultural", "sports", "academic"]
user_sessions = {}

def get_response(message, session_id):
    # Detect interest
    result = classifier(message, candidate_labels=categories)
    top_interest = result['labels'][0]
    
    # Find matching events
    matching_events = [e for e in events if e["category"] == top_interest]
    
    if "upcoming" in message.lower():
        upcoming = [e for e in events if "May" in e["date"]][:3]
        return f"📅 Upcoming events: {', '.join([e['name'] for e in upcoming])}"
    
    elif "trending" in message.lower() or "popular" in message.lower():
        trending = sorted(events, key=lambda x: x['registered']/x['capacity'], reverse=True)[:3]
        return f"🔥 Trending events: {', '.join([e['name'] for e in trending])}"
    
    elif "help" in message.lower():
        return """🤖 I can help you with:
• Finding events based on your interests
• Showing upcoming events
• Trending/popular events
• Event details

Try: "I love coding", "Show career events", or "What's trending?" """
    
    elif matching_events:
        event = matching_events[0]
        return f"🎯 Based on your interest in {top_interest}:\n📌 {event['name']} - {event['date']}\n📝 {event['description']}\n👥 {event['registered']}/{event['capacity']} registered"
    
    else:
        return f"I see you're interested in {top_interest}. Tell me more about what you're looking for!"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        message = data.get('message', '')
        session_id = data.get('session_id', str(uuid.uuid4()))
        
        response = get_response(message, session_id)
        
        return jsonify({
            'success': True,
            'response': response,
            'session_id': session_id
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/events', methods=['GET'])
def get_events():
    category = request.args.get('category')
    if category:
        filtered = [e for e in events if e['category'] == category]
    else:
        filtered = events
    return jsonify(filtered)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)