from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
import uuid

app = Flask(__name__)
CORS(app)

events = {
    "technical": [
        "AI & Machine Learning Workshop - May 15",
        "Python Programming Bootcamp - May 17",
        "Hackathon 2024 - May 24-26"
    ],
    "career": [
        "Annual Career Fair - May 20",
        "Networking Night with Alumni - May 23"
    ],
    "cultural": [
        "Spring Cultural Festival - May 25",
        "Diwali Celebration - May 19"
    ],
    "sports": [
        "Basketball Tournament - May 18",
        "Yoga & Wellness Retreat - May 21"
    ]
}

def get_response(message):
    msg = message.lower()
    
    if "technical" in msg or "coding" in msg:
        return "Technical events: " + ", ".join(events["technical"])
    elif "career" in msg or "job" in msg:
        return "Career events: " + ", ".join(events["career"])
    elif "cultural" in msg:
        return "Cultural events: " + ", ".join(events["cultural"])
    elif "sports" in msg:
        return "Sports events: " + ", ".join(events["sports"])
    elif "upcoming" in msg:
        return "Upcoming: AI Workshop (May 15), Career Fair (May 20), Cultural Fest (May 25)"
    else:
        return "Tell me your interest (technical, career, cultural, sports) or ask for 'upcoming' events!"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    response = get_response(data.get('message', ''))
    return jsonify({'response': response})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
