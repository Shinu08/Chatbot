from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import os
import uuid
import re
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

# Sample events database
events = [
    {"id": 1, "name": "AI & Machine Learning Workshop", "category": "technical", 
     "date": "May 15, 2024", "description": "Learn AI fundamentals with hands-on projects", 
     "capacity": 50, "registered": 32, "time": "2:00 PM", "location": "CS Building 101"},
    
    {"id": 2, "name": "Annual Career Fair 2024", "category": "career", 
     "date": "May 20, 2024", "description": "Meet recruiters from Google, Microsoft, and top companies", 
     "capacity": 200, "registered": 156, "time": "10:00 AM", "location": "Student Center"},
    
    {"id": 3, "name": "Spring Cultural Festival", "category": "cultural", 
     "date": "May 25, 2024", "description": "Celebrate diversity with music, dance, and food", 
     "capacity": 500, "registered": 320, "time": "4:00 PM", "location": "University Quad"},
    
    {"id": 4, "name": "Inter-University Basketball Tournament", "category": "sports", 
     "date": "May 18, 2024", "description": "Compete against teams from 10 universities", 
     "capacity": 300, "registered": 178, "time": "9:00 AM", "location": "Sports Complex"},
    
    {"id": 5, "name": "Research Symposium 2024", "category": "academic", 
     "date": "May 22, 2024", "description": "Showcase your research and win prizes", 
     "capacity": 150, "registered": 95, "time": "11:00 AM", "location": "Convention Hall"},
    
    {"id": 6, "name": "Python Programming Bootcamp", "category": "technical", 
     "date": "May 17, 2024", "description": "3-day intensive Python coding workshop", 
     "capacity": 40, "registered": 28, "time": "10:00 AM", "location": "CS Lab 304"},
    
    {"id": 7, "name": "Networking Night with Alumni", "category": "career", 
     "date": "May 23, 2024", "description": "Connect with successful alumni from tech industry", 
     "capacity": 100, "registered": 67, "time": "6:00 PM", "location": "Alumni Center"},
    
    {"id": 8, "name": "Diwali Celebration", "category": "cultural", 
     "date": "May 19, 2024", "description": "Traditional Indian festival celebration", 
     "capacity": 250, "registered": 189, "time": "7:00 PM", "location": "Student Union"},
    
    {"id": 9, "name": "Yoga & Wellness Retreat", "category": "sports", 
     "date": "May 21, 2024", "description": "Mindfulness and stress relief workshop", 
     "capacity": 60, "registered": 42, "time": "8:00 AM", "location": "Wellness Center"},
    
    {"id": 10, "name": "Hackathon 2024", "category": "technical", 
     "date": "May 24-26, 2024", "description": "48-hour coding competition", 
     "capacity": 100, "registered": 73, "time": "9:00 AM", "location": "Innovation Hub"},
]

# Interest keywords mapping
interest_map = {
    "technical": ["coding", "programming", "ai", "machine learning", "hackathon", "python", "tech", "software", "developer", "computer"],
    "career": ["job", "internship", "career", "placement", "recruitment", "company", "interview", "resume", "networking"],
    "cultural": ["cultural", "festival", "music", "dance", "art", "performance", "celebration", "traditional", "food"],
    "sports": ["sports", "basketball", "tournament", "fitness", "yoga", "game", "athletics", "competition", "wellness"],
    "academic": ["research", "symposium", "academic", "study", "paper", "conference", "seminar", "workshop"]
}

def detect_interest(message):
    """Detect user interest from message using keyword matching"""
    message_lower = message.lower()
    scores = {}
    
    for category, keywords in interest_map.items():
        score = sum(1 for keyword in keywords if keyword in message_lower)
        if score > 0:
            scores[category] = score
    
    if scores:
        return max(scores, key=scores.get)
    return None

def get_response(message, session_id):
    """Generate response based on user message"""
    message_lower = message.lower()
    
    # Check for help
    if "help" in message_lower:
        return """🤖 **I can help you with:**

• **Find events by interest**: "I love coding", "Show me career events"
• **Upcoming events**: "What's happening this week?"
• **Trending events**: "What's popular?" or "Trending events"
• **Event details**: "Tell me about AI workshop"
• **Register**: "Register for event 1"

What would you like to know about?"""
    
    # Check for specific event queries
    for event in events:
        if event['name'].lower() in message_lower:
            return f"""📌 **{event['name']}**
📅 Date: {event['date']}
🕒 Time: {event['time']}
📍 Location: {event['location']}
📝 Description: {event['description']}
👥 Attendance: {event['registered']}/{event['capacity']} registered

Type "Register for event {event['id']}" to join!"""
    
    # Check for registration
    if "register" in message_lower:
        numbers = re.findall(r'\d+', message)
        if numbers:
            event_id = int(numbers[0])
            event = next((e for e in events if e['id'] == event_id), None)
            if event:
                if event['registered'] < event['capacity']:
                    event['registered'] += 1
                    return f"✅ Successfully registered for **{event['name']}**! You'll receive a confirmation email shortly."
                else:
                    return f"❌ Sorry, **{event['name']}** is already full! Check out other events."
            else:
                return f"❌ Event with ID {event_id} not found. Available events: {', '.join([str(e['id']) for e in events])}"
        else:
            return "Please specify the event ID. Example: 'Register for event 1'"
    
    # Check for upcoming events
    if "upcoming" in message_lower or "this week" in message_lower:
        upcoming = events[:5]
        response = "📅 **Upcoming Events:**\n\n"
        for event in upcoming:
            response += f"**{event['name']}** - {event['date']}\n"
            response += f"📝 {event['description'][:100]}...\n"
            response += f"👥 {event['registered']}/{event['capacity']} spots filled\n\n"
        return response
    
    # Check for trending/popular events
    if "trending" in message_lower or "popular" in message_lower:
        trending = sorted(events, key=lambda x: x['registered']/x['capacity'], reverse=True)[:3]
        response = "🔥 **Trending Events:**\n\n"
        for event in trending:
            popularity = int((event['registered']/event['capacity']) * 100)
            response += f"**{event['name']}** - {popularity}% full\n"
            response += f"📅 {event['date']}\n\n"
        return response
    
    # Check for category-based queries
    if "technical" in message_lower or "coding" in message_lower or "programming" in message_lower:
        category = "technical"
    elif "career" in message_lower or "job" in message_lower:
        category = "career"
    elif "cultural" in message_lower or "festival" in message_lower:
        category = "cultural"
    elif "sports" in message_lower:
        category = "sports"
    elif "academic" in message_lower or "research" in message_lower:
        category = "academic"
    else:
        # Detect interest from message
        category = detect_interest(message)
    
    if category:
        matching_events = [e for e in events if e['category'] == category]
        if matching_events:
            response = f"🎯 **{category.title()} Events You Might Like:**\n\n"
            for event in matching_events[:3]:
                response += f"📌 **{event['name']}**\n"
                response += f"   📅 {event['date']} at {event['time']}\n"
                response += f"   📍 {event['location']}\n"
                response += f"   👥 {event['registered']}/{event['capacity']} registered\n\n"
            response += f"💡 To register, type: Register for event [ID]\n"
            response += f"🔍 For more details, ask: Tell me about [event name]"
            return response
    
    # Default response with suggestions
    return """🎓 **Welcome to University Event Assistant!**

I can help you find events based on your interests. Try asking:

• **"I love coding and AI"** - Find technical events
• **"Show me career opportunities"** - Career fairs & networking
• **"What cultural events?"** - Cultural festivals
• **"Sports events near me"** - Tournaments & fitness
• **"What's trending?"** - Most popular events
• **"Upcoming events"** - What's happening soon

What interests you? Let me know and I'll find perfect events for you! 🎉"""
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

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'events': len(events)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
