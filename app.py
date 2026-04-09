from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import re
from datetime import datetime
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False
CORS(app)

# ============= RAILWAY DATABASE CONFIGURATION =============
# Railway automatically injects these environment variables
# For local testing, you can set them manually or use a .env file
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', os.environ.get('MYSQLHOST', 'localhost')),
    'database': os.environ.get('DB_NAME', os.environ.get('MYSQLDATABASE', 'chatbot')),
    'user': os.environ.get('DB_USER', os.environ.get('MYSQLUSER', 'root')),
    'password': os.environ.get('DB_PASSWORD', os.environ.get('MYSQLPASSWORD', '')),
    'port': int(os.environ.get('DB_PORT', os.environ.get('MYSQLPORT', 3306)))
}

def get_db_connection():
    """Create database connection for Railway"""
    try:
        # Print debug info (remove in production)
        print(f"Connecting to: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
        print(f"Database: {DB_CONFIG['database']}")
        print(f"User: {DB_CONFIG['user']}")
        
        connection = mysql.connector.connect(
            host=DB_CONFIG['host'],
            database=DB_CONFIG['database'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            port=DB_CONFIG['port'],
            connect_timeout=10,
            use_pure=True
        )
        if connection.is_connected():
            print("✅ Connected to Railway MySQL database")
        return connection
    except Error as e:
        print(f"Database connection error: {e}")
        return None

def get_events_from_db(category=None, event_id=None):
    """Fetch events from database and format them to match original API structure"""
    connection = get_db_connection()
    if not connection:
        print("No database connection, using fallback data")
        return [] if not event_id else None
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        if event_id:
            query = """
                SELECT e.*, ec.name as category_name 
                FROM events e
                JOIN event_categories ec ON e.event_category_id = ec.id
                WHERE e.id = %s AND e.status = 'approved'
            """
            cursor.execute(query, (event_id,))
            result = cursor.fetchone()
            if result:
                # Format database event to match original API structure
                return format_event_for_api(result)
            return None
        
        elif category:
            # Map category names to your database categories
            category_map = {
                'technical': 'Technology',
                'career': 'Careet & Learning',
                'cultural': 'Entertainment',
                'sports': 'Sports',
                'academic': 'Arts & Creativity'
            }
            db_category = category_map.get(category, category)
            
            query = """
                SELECT e.*, ec.name as category_name,
                       (SELECT COUNT(*) FROM event_registrations WHERE event_id = e.id) as registered_count
                FROM events e
                JOIN event_categories ec ON e.event_category_id = ec.id
                WHERE ec.name LIKE %s AND e.status = 'approved'
                ORDER BY e.start_datetime ASC
            """
            cursor.execute(query, (f'%{db_category}%',))
            results = cursor.fetchall()
            return [format_event_for_api(event) for event in results]
        
        else:
            query = """
                SELECT e.*, ec.name as category_name,
                       (SELECT COUNT(*) FROM event_registrations WHERE event_id = e.id) as registered_count
                FROM events e
                JOIN event_categories ec ON e.event_category_id = ec.id
                WHERE e.status = 'approved'
                ORDER BY e.start_datetime ASC
            """
            cursor.execute(query)
            results = cursor.fetchall()
            return [format_event_for_api(event) for event in results]
            
    except Error as err:
        print(f"Database error: {err}")
        return [] if not event_id else None
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def format_event_for_api(db_event):
    """Convert database event format to match original API event structure"""
    # Format date from datetime to readable string
    start_date = db_event['start_datetime']
    if isinstance(start_date, datetime):
        date_str = start_date.strftime("%B %d, %Y")
        time_str = start_date.strftime("%I:%M %p")
    else:
        date_str = str(start_date) if start_date else "Date TBA"
        time_str = "Time TBA"
    
    # Map category ID to category name
    category_map = {
        1: 'entertainment',
        2: 'career',
        3: 'arts',
        4: 'wellness',
        5: 'technology',
        6: 'sports',
        7: 'lifestyle'
    }
    
    # Get category name from event_categories table or use mapping
    if 'category_name' in db_event and db_event['category_name']:
        category_lower = db_event['category_name'].lower()
        if 'technology' in category_lower:
            category = 'technical'
        elif 'careet' in category_lower or 'learning' in category_lower:
            category = 'career'
        elif 'entertainment' in category_lower:
            category = 'cultural'
        elif 'sports' in category_lower:
            category = 'sports'
        elif 'arts' in category_lower:
            category = 'academic'
        else:
            category = category_lower
    else:
        category = category_map.get(db_event.get('event_category_id', 1), 'technical')
    
    # Get registered count
    registered = db_event.get('registered_count', 0)
    
    return {
        "id": db_event['id'],
        "name": db_event['title'],
        "category": category,
        "date": date_str,
        "time": time_str,
        "location": db_event['venue'],
        "description": db_event['description'],
        "capacity": db_event['max_participants'] if db_event['max_participants'] else 999,
        "registered": registered,
        "speaker": db_event.get('created_by', 'University Organizer'),
        "tags": [db_event.get('category_name', 'Event'), db_event.get('mode', 'offline')],
        "price": "Free" if db_event.get('mode') == 'offline' else "Check website",
        "mode": db_event['mode'],
        "meeting_link": db_event.get('meeting_link'),
        "registration_deadline": db_event['registration_deadline'].strftime("%B %d, %Y") if db_event['registration_deadline'] else None
    }

def get_upcoming_events_from_db(days=30):
    """Get events happening in next N days"""
    connection = get_db_connection()
    if not connection:
        return []
    
    try:
        cursor = connection.cursor(dictionary=True)
        query = """
            SELECT e.*, ec.name as category_name,
                   (SELECT COUNT(*) FROM event_registrations WHERE event_id = e.id) as registered_count
            FROM events e
            JOIN event_categories ec ON e.event_category_id = ec.id
            WHERE e.start_datetime BETWEEN NOW() AND DATE_ADD(NOW(), INTERVAL %s DAY)
            AND e.status = 'approved'
            ORDER BY e.start_datetime ASC
        """
        cursor.execute(query, (days,))
        results = cursor.fetchall()
        return [format_event_for_api(event) for event in results]
    except Error as err:
        print(f"Database error: {err}")
        return []
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def get_trending_events_from_db(limit=5):
    """Get most popular events based on registrations"""
    connection = get_db_connection()
    if not connection:
        return []
    
    try:
        cursor = connection.cursor(dictionary=True)
        query = """
            SELECT e.*, ec.name as category_name,
                   COUNT(er.id) as registration_count,
                   (SELECT COUNT(*) FROM event_registrations WHERE event_id = e.id) as registered_count
            FROM events e
            JOIN event_categories ec ON e.event_category_id = ec.id
            LEFT JOIN event_registrations er ON e.id = er.event_id
            WHERE e.status = 'approved'
            GROUP BY e.id
            ORDER BY registration_count DESC
            LIMIT %s
        """
        cursor.execute(query, (limit,))
        results = cursor.fetchall()
        return [format_event_for_api(event) for event in results]
    except Error as err:
        print(f"Database error: {err}")
        return []
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def register_student_for_event_db(event_id, student_id):
    """Register a student for an event in database"""
    connection = get_db_connection()
    if not connection:
        return False, "Database connection failed"
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Check if event exists and has capacity
        cursor.execute("""
            SELECT max_participants, title,
                   (SELECT COUNT(*) FROM event_registrations WHERE event_id = %s) as current_registrations
            FROM events WHERE id = %s AND status = 'approved'
        """, (event_id, event_id))
        
        event = cursor.fetchone()
        
        if not event:
            return False, "Event not found"
        
        if event['max_participants'] and event['current_registrations'] >= event['max_participants']:
            return False, f"Sorry, {event['title']} is full"
        
        # Check if already registered
        cursor.execute("""
            SELECT id FROM event_registrations 
            WHERE event_id = %s AND student_id = %s
        """, (event_id, student_id))
        
        if cursor.fetchone():
            return False, "Already registered for this event"
        
        # Generate registration ID
        cursor.execute("SELECT COUNT(*) as count FROM event_registrations")
        count = cursor.fetchone()['count']
        reg_id = f"EVT-{str(count + 1).zfill(4)}"
        
        # Register student
        cursor.execute("""
            INSERT INTO event_registrations (event_id, student_id, reg_id, status, created_at, updated_at)
            VALUES (%s, %s, %s, 'approved', NOW(), NOW())
        """, (event_id, student_id, reg_id))
        
        connection.commit()
        return True, f"✅ Successfully registered for {event['title']}! Registration ID: {reg_id}"
        
    except Error as err:
        print(f"Database error: {err}")
        return False, f"Database error: {err}"
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def get_event_categories_from_db():
    """Get all event categories from database"""
    connection = get_db_connection()
    if not connection:
        return []
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id, name, slug FROM event_categories WHERE is_active = 1")
        return cursor.fetchall()
    except Error as err:
        print(f"Database error: {err}")
        return []
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def get_db_stats():
    """Get statistics from database"""
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute("SELECT COUNT(*) as total FROM events WHERE status = 'approved'")
        total_events = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(*) as total FROM event_registrations")
        total_registrations = cursor.fetchone()['total']
        
        cursor.execute("SELECT SUM(max_participants) as total FROM events WHERE status = 'approved'")
        total_capacity = cursor.fetchone()['total'] or 0
        
        return {
            'total_events': total_events,
            'total_registrations': total_registrations,
            'total_capacity': total_capacity,
            'average_fill_rate': round((total_registrations / total_capacity) * 100, 2) if total_capacity > 0 else 0
        }
    except Error as err:
        print(f"Database error: {err}")
        return None
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# ============= FALLBACK EVENT DATABASE (in case database is not available) =============
EVENTS = [
    {
        "id": 1,
        "name": "Plantation Programme",
        "category": "wellness",
        "date": "March 31, 2026",
        "time": "06:00 AM - 10:00 AM",
        "location": "RPJ College",
        "description": "Planting Trees in nearby areas",
        "capacity": 250,
        "registered": 0,
        "speaker": "Admin",
        "tags": ["Health", "Wellness", "Environment"],
        "price": "Free",
        "mode": "offline"
    },
    {
        "id": 2,
        "name": "Internship & Training Programme",
        "category": "career",
        "date": "April 1, 2026",
        "time": "12:00 PM",
        "location": "RPJ College - Online Mode",
        "description": "Internship & Training Opportunity to all the students",
        "capacity": 150,
        "registered": 1,
        "speaker": "Admin",
        "tags": ["Career", "Internship", "Training"],
        "price": "Free",
        "mode": "online",
        "meeting_link": "https://randomdailyurls.com/"
    },
    {
        "id": 3,
        "name": "Sports Day Event",
        "category": "sports",
        "date": "April 15, 2026",
        "time": "09:00 AM",
        "location": "JK Sports Ground",
        "description": "Sports Day Organized in JK University",
        "capacity": 800,
        "registered": 1,
        "speaker": "Admin",
        "tags": ["Sports", "Tournament"],
        "price": "Free",
        "mode": "offline"
    },
    {
        "id": 4,
        "name": "Arts Festival 2026",
        "category": "arts",
        "date": "April 25, 2026",
        "time": "03:00 PM - 04:30 PM",
        "location": "Indus University, Auditorium Hall",
        "description": "Arts Competition organized in our college",
        "capacity": 90,
        "registered": 1,
        "speaker": "Admin",
        "tags": ["Arts", "Creativity", "Festival"],
        "price": "Free",
        "mode": "offline"
    }
]

user_sessions = {}

INTEREST_MAP = {
    "technical": ["coding", "programming", "ai", "machine learning", "hackathon", "python", "tech", "software", "developer", "computer", "data science", "technology"],
    "career": ["job", "internship", "career", "placement", "recruitment", "company", "interview", "resume", "networking", "salary", "employment", "training"],
    "cultural": ["cultural", "festival", "music", "dance", "art", "performance", "celebration", "traditional", "food", "concert", "show", "entertainment"],
    "sports": ["sports", "basketball", "tournament", "fitness", "yoga", "game", "athletics", "competition", "wellness", "exercise", "workout"],
    "academic": ["research", "symposium", "academic", "study", "paper", "conference", "seminar", "workshop", "presentation", "thesis"],
    "wellness": ["health", "wellness", "plantation", "environment", "green", "nature"]
}

def detect_interest(message):
    message_lower = message.lower()
    scores = {}
    
    for category, keywords in INTEREST_MAP.items():
        score = sum(2 if keyword in message_lower else 0 for keyword in keywords)
        if score > 0:
            scores[category] = score
    
    if scores:
        return max(scores, key=scores.get)
    return None

def generate_response(message, user_id=None):
    msg_lower = message.lower()
    
    if any(word in msg_lower for word in ["help", "commands", "what can you do"]):
        return {
            "response": "Available Commands:\n\n"
                       "📌 Find Events:\n"
                       "• 'Show technical events' - Technology events\n"
                       "• 'Show career events' - Internships, training\n"
                       "• 'Show sports events' - Sports tournaments\n"
                       "• 'Show wellness events' - Health, plantation\n"
                       "• 'Show arts events' - Cultural, arts festival\n\n"
                       "🔍 Browse:\n"
                       "• 'Upcoming events' - Events happening soon\n"
                       "• 'Trending events' - Most popular events\n"
                       "• 'All events' - List all events\n\n"
                       "📝 Register:\n"
                       "• 'Register for event 1' - Register for specific event\n\n"
                       "ℹ️ Details:\n"
                       "• 'Tell me about Plantation Programme' - Get event details",
            "intent": "help"
        }
    
    if "register" in msg_lower:
        numbers = re.findall(r'\d+', message)
        if numbers:
            event_id = int(numbers[0])
            student_id = 1
            success, result = register_student_for_event_db(event_id, student_id)
            
            if success:
                return {"response": result, "intent": "registration"}
            else:
                event = next((e for e in EVENTS if e['id'] == event_id), None)
                if event:
                    if event['registered'] < event['capacity']:
                        event['registered'] += 1
                        return {"response": f"✅ Successfully registered for {event['name']}!", "event": event, "intent": "registration"}
                    else:
                        return {"response": f"❌ Sorry, {event['name']} is full!", "intent": "registration_failed"}
                else:
                    return {"response": f"❌ Event with ID {event_id} not found.", "intent": "registration_failed"}
        else:
            return {"response": "Please specify event ID. Example: 'Register for event 1'", "intent": "registration_help"}
    
    # Try database first for event details
    db_events = get_events_from_db()
    if db_events:
        for event in db_events:
            if event.get('name', '').lower() in msg_lower:
                return {"response": event, "intent": "event_details"}
    else:
        for event in EVENTS:
            if event['name'].lower() in msg_lower:
                return {"response": event, "intent": "event_details"}
    
    if any(word in msg_lower for word in ["upcoming", "this week", "soon"]):
        db_upcoming = get_upcoming_events_from_db(30)
        if db_upcoming:
            return {"response": db_upcoming, "intent": "upcoming_events", "count": len(db_upcoming)}
        else:
            return {"response": EVENTS[:5], "intent": "upcoming_events", "count": len(EVENTS[:5])}
    
    if any(word in msg_lower for word in ["trending", "popular", "hot"]):
        db_trending = get_trending_events_from_db(3)
        if db_trending:
            return {"response": db_trending, "intent": "trending_events"}
        else:
            trending = sorted(EVENTS, key=lambda x: x['registered']/x['capacity'], reverse=True)[:3]
            return {"response": trending, "intent": "trending_events"}
    
    if "all events" in msg_lower or "list all" in msg_lower:
        db_all = get_events_from_db()
        if db_all:
            return {"response": db_all, "intent": "all_events", "count": len(db_all)}
        else:
            return {"response": EVENTS, "intent": "all_events", "count": len(EVENTS)}
    
    categories = {
        "technical": ["technical", "coding", "programming", "ai", "hackathon", "technology"],
        "career": ["career", "job", "internship", "placement", "training"],
        "sports": ["sports", "basketball", "tournament", "fitness", "yoga", "game"],
        "wellness": ["wellness", "health", "plantation", "environment", "nature"],
        "arts": ["arts", "cultural", "festival", "music", "dance", "entertainment"]
    }
    
    for category, keywords in categories.items():
        if any(keyword in msg_lower for keyword in keywords):
            db_filtered = get_events_from_db(category=category)
            if db_filtered:
                return {"response": db_filtered, "intent": f"{category}_events", "category": category, "count": len(db_filtered)}
            else:
                filtered = [e for e in EVENTS if e['category'] == category]
                return {"response": filtered, "intent": f"{category}_events", "category": category, "count": len(filtered)}
    
    interest = detect_interest(message)
    if interest:
        db_interest = get_events_from_db(category=interest)
        if db_interest:
            return {"response": db_interest, "intent": "recommended_events", "interest": interest, "count": len(db_interest)}
        else:
            filtered = [e for e in EVENTS if e['category'] == interest]
            if filtered:
                return {"response": filtered, "intent": "recommended_events", "interest": interest, "count": len(filtered)}
    
    if any(word in msg_lower for word in ["hello", "hi", "hey"]):
        return {"response": "Hello! I'm your University Event Assistant. Type 'help' to see what I can do!", "intent": "greeting"}
    
    return {"response": "I'm not sure about that. Type 'help' to see all commands or tell me what events you're interested in!", "intent": "unknown"}

# ============= API ENDPOINTS =============

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400
        
        message = data.get('message', '').strip()
        user_id = data.get('user_id', None)
        
        if not message:
            return jsonify({'success': False, 'error': 'Message is required'}), 400
        
        result = generate_response(message, user_id)
        return jsonify({'success': True, 'message': message, **result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/events', methods=['GET'])
def get_events():
    try:
        category = request.args.get('category')
        event_id = request.args.get('id')
        
        if event_id:
            db_event = get_events_from_db(event_id=int(event_id))
            if db_event:
                return jsonify({'success': True, 'event': db_event})
            event = next((e for e in EVENTS if e['id'] == int(event_id)), None)
            if event:
                return jsonify({'success': True, 'event': event})
            return jsonify({'success': False, 'error': 'Event not found'}), 404
        
        if category:
            db_filtered = get_events_from_db(category=category)
            if db_filtered:
                return jsonify({'success': True, 'events': db_filtered, 'count': len(db_filtered), 'category': category})
            filtered = [e for e in EVENTS if e['category'].lower() == category.lower()]
            return jsonify({'success': True, 'events': filtered, 'count': len(filtered), 'category': category})
        
        db_events = get_events_from_db()
        if db_events:
            return jsonify({'success': True, 'events': db_events, 'count': len(db_events)})
        return jsonify({'success': True, 'events': EVENTS, 'count': len(EVENTS)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/events/<int:event_id>', methods=['GET'])
def get_event_by_id(event_id):
    try:
        db_event = get_events_from_db(event_id=event_id)
        if db_event:
            return jsonify({'success': True, 'event': db_event})
        event = next((e for e in EVENTS if e['id'] == event_id), None)
        if event:
            return jsonify({'success': True, 'event': event})
        return jsonify({'success': False, 'error': 'Event not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/events/<int:event_id>/register', methods=['POST'])
def register_for_event(event_id):
    try:
        data = request.get_json()
        student_id = data.get('student_id', 1) if data else 1
        
        success, message = register_student_for_event_db(event_id, student_id)
        if success:
            return jsonify({'success': True, 'message': message})
        
        event = next((e for e in EVENTS if e['id'] == event_id), None)
        if not event:
            return jsonify({'success': False, 'error': 'Event not found'}), 404
        if event['registered'] >= event['capacity']:
            return jsonify({'success': False, 'error': f'Sorry, {event["name"]} is full'}), 400
        
        event['registered'] += 1
        return jsonify({'success': True, 'message': f'Successfully registered for {event["name"]}', 'event': event})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/categories', methods=['GET'])
def get_categories():
    db_categories = get_event_categories_from_db()
    if db_categories:
        return jsonify({'success': True, 'categories': [c['name'] for c in db_categories]})
    categories = list(set([e['category'] for e in EVENTS]))
    return jsonify({'success': True, 'categories': categories})

@app.route('/api/stats', methods=['GET'])
def get_stats():
    db_stats = get_db_stats()
    if db_stats:
        return jsonify({'success': True, 'stats': db_stats})
    total_events = len(EVENTS)
    total_registrations = sum(e['registered'] for e in EVENTS)
    total_capacity = sum(e['capacity'] for e in EVENTS)
    return jsonify({'success': True, 'stats': {'total_events': total_events, 'total_registrations': total_registrations, 'total_capacity': total_capacity, 'average_fill_rate': round((total_registrations / total_capacity) * 100, 2)}})

@app.route('/health', methods=['GET'])
def health_check():
    db_status = "connected" if get_db_connection() else "disconnected"
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat(), 'events_count': len(EVENTS), 'version': '1.0.0', 'database': db_status})

@app.route('/', methods=['GET'])
def root():
    return jsonify({
        'name': 'University Event Chatbot API',
        'version': '1.0.0',
        'description': 'AI-powered event management chatbot for universities',
        'endpoints': {
            'POST /api/chat': 'Send messages to chatbot',
            'GET /api/events': 'Get all events',
            'GET /api/events?category=technical': 'Filter events by category',
            'GET /api/events/{id}': 'Get specific event by ID',
            'POST /api/events/{id}/register': 'Register for an event',
            'GET /api/categories': 'Get all event categories',
            'GET /api/stats': 'Get API statistics',
            'GET /health': 'Health check'
        }
    })

@app.route('/debug/env', methods=['GET'])
def debug_env():
    """Debug endpoint to check environment variables (remove in production)"""
    return jsonify({
        'DB_HOST': os.environ.get('DB_HOST', 'mysql.railway.internal'),
        'DB_NAME': os.environ.get('DB_NAME', 'evently_db'),
        'DB_USER': os.environ.get('DB_USER', 'root'),
        'DB_PORT': os.environ.get('DB_PORT', '3306'),
        'MYSQLHOST': os.environ.get('MYSQLHOST', 'mysql.railway.internal'),
        'MYSQLDATABASE': os.environ.get('MYSQLDATABASE', 'railway'),
        'MYSQLUSER': os.environ.get('MYSQLUSER', 'root'),
        'MYSQLPORT': os.environ.get('MYSQLPORT', '3306'),
        'database_configured': all([DB_CONFIG['host'] != 'localhost', DB_CONFIG['user'] != 'root'])
    })

@app.errorhandler(404)
def not_found(e):
    return jsonify({'success': False, 'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'success': False, 'error': 'Internal server error'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
