from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import re
from datetime import datetime
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False
CORS(app)  # Enable CORS for all routes

# ============= DATABASE CONFIGURATION =============
# Add your database credentials here
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'database': os.environ.get('DB_NAME', 'evently_db'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', ''),
    'port': int(os.environ.get('DB_PORT', 3306))
}

def get_db_connection():
    """Create database connection"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"Database connection error: {e}")
        return None

def get_events_from_db(category=None, event_id=None):
    """Fetch events from database"""
    connection = get_db_connection()
    if not connection:
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
            return cursor.fetchone()
        
        elif category:
            query = """
                SELECT e.*, ec.name as category_name 
                FROM events e
                JOIN event_categories ec ON e.event_category_id = ec.id
                WHERE ec.name LIKE %s AND e.status = 'approved'
                ORDER BY e.start_datetime ASC
            """
            cursor.execute(query, (f'%{category}%',))
            return cursor.fetchall()
        
        else:
            query = """
                SELECT e.*, ec.name as category_name 
                FROM events e
                JOIN event_categories ec ON e.event_category_id = ec.id
                WHERE e.status = 'approved'
                ORDER BY e.start_datetime ASC
            """
            cursor.execute(query)
            return cursor.fetchall()
            
    except Error as err:
        print(f"Database error: {err}")
        return [] if not event_id else None
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def get_upcoming_events_from_db(days=30):
    """Get events happening in next N days"""
    connection = get_db_connection()
    if not connection:
        return []
    
    try:
        cursor = connection.cursor(dictionary=True)
        query = """
            SELECT e.*, ec.name as category_name 
            FROM events e
            JOIN event_categories ec ON e.event_category_id = ec.id
            WHERE e.start_datetime BETWEEN NOW() AND DATE_ADD(NOW(), INTERVAL %s DAY)
            AND e.status = 'approved'
            ORDER BY e.start_datetime ASC
        """
        cursor.execute(query, (days,))
        return cursor.fetchall()
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
                   COUNT(er.id) as registration_count
            FROM events e
            JOIN event_categories ec ON e.event_category_id = ec.id
            LEFT JOIN event_registrations er ON e.id = er.event_id
            WHERE e.status = 'approved'
            GROUP BY e.id
            ORDER BY registration_count DESC
            LIMIT %s
        """
        cursor.execute(query, (limit,))
        return cursor.fetchall()
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
            SELECT max_participants, 
                   (SELECT COUNT(*) FROM event_registrations WHERE event_id = %s) as current_registrations
            FROM events WHERE id = %s AND status = 'approved'
        """, (event_id, event_id))
        
        event = cursor.fetchone()
        
        if not event:
            return False, "Event not found"
        
        if event['max_participants'] and event['current_registrations'] >= event['max_participants']:
            return False, "Event is full"
        
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
        return True, f"Successfully registered! Your Registration ID: {reg_id}"
        
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
        
        # Get total events
        cursor.execute("SELECT COUNT(*) as total FROM events WHERE status = 'approved'")
        total_events = cursor.fetchone()['total']
        
        # Get total registrations
        cursor.execute("SELECT COUNT(*) as total FROM event_registrations")
        total_registrations = cursor.fetchone()['total']
        
        # Get total capacity
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

# ============= EVENT DATABASE (Fallback if no DB connection) =============
EVENTS = [
    {
        "id": 1,
        "name": "AI & Machine Learning Workshop",
        "category": "technical",
        "date": "May 15, 2024",
        "time": "2:00 PM - 5:00 PM",
        "location": "Computer Science Building, Room 101",
        "description": "Hands-on workshop covering neural networks, deep learning, and practical AI applications.",
        "capacity": 50,
        "registered": 32,
        "speaker": "Dr. Sarah Johnson",
        "tags": ["AI", "Machine Learning", "Python"],
        "price": "Free"
    },
    {
        "id": 2,
        "name": "Annual Career Fair 2024",
        "category": "career",
        "date": "May 20, 2024",
        "time": "10:00 AM - 4:00 PM",
        "location": "Student Center Grand Ballroom",
        "description": "Meet recruiters from Google, Microsoft, Amazon, and 50+ top companies.",
        "capacity": 500,
        "registered": 387,
        "speaker": "Various Recruiters",
        "tags": ["Career", "Jobs", "Networking"],
        "price": "Free"
    },
    {
        "id": 3,
        "name": "Spring Cultural Festival",
        "category": "cultural",
        "date": "May 25, 2024",
        "time": "4:00 PM - 9:00 PM",
        "location": "University Quad",
        "description": "Celebrate diversity with international food, music performances, and dance shows.",
        "capacity": 1000,
        "registered": 723,
        "speaker": "Cultural Groups",
        "tags": ["Cultural", "Music", "Food"],
        "price": "Free"
    },
    {
        "id": 4,
        "name": "Inter-University Basketball Tournament",
        "category": "sports",
        "date": "May 18-19, 2024",
        "time": "9:00 AM - 6:00 PM",
        "location": "Sports Complex Arena",
        "description": "Annual basketball tournament with 15 universities competing.",
        "capacity": 800,
        "registered": 542,
        "speaker": "Professional Coaches",
        "tags": ["Sports", "Basketball", "Tournament"],
        "price": "$10 per day"
    },
    {
        "id": 5,
        "name": "Research Symposium 2024",
        "category": "academic",
        "date": "May 22, 2024",
        "time": "9:00 AM - 5:00 PM",
        "location": "Convention Center Hall A",
        "description": "Showcase your research projects and attend keynote speeches.",
        "capacity": 300,
        "registered": 187,
        "speaker": "Dr. Robert Chen",
        "tags": ["Research", "Academic", "Symposium"],
        "price": "Free"
    },
    {
        "id": 6,
        "name": "Python Programming Bootcamp",
        "category": "technical",
        "date": "May 17-19, 2024",
        "time": "10:00 AM - 4:00 PM",
        "location": "CS Building, Lab 304",
        "description": "3-day intensive bootcamp covering Python basics to advanced concepts.",
        "capacity": 40,
        "registered": 38,
        "speaker": "Prof. Alex Kumar",
        "tags": ["Python", "Programming", "Bootcamp"],
        "price": "$50"
    },
    {
        "id": 7,
        "name": "Networking Night with Alumni",
        "category": "career",
        "date": "May 23, 2024",
        "time": "6:00 PM - 9:00 PM",
        "location": "Alumni Center",
        "description": "Connect with successful alumni working at top tech companies.",
        "capacity": 150,
        "registered": 112,
        "speaker": "Alumni Panel",
        "tags": ["Networking", "Career", "Alumni"],
        "price": "Free"
    },
    {
        "id": 8,
        "name": "Diwali Celebration Night",
        "category": "cultural",
        "date": "May 19, 2024",
        "time": "7:00 PM - 11:00 PM",
        "location": "Student Union Ballroom",
        "description": "Traditional Indian festival celebration with music, dance, and food.",
        "capacity": 400,
        "registered": 312,
        "speaker": "Cultural Performers",
        "tags": ["Cultural", "Diwali", "Festival"],
        "price": "Free"
    },
    {
        "id": 9,
        "name": "Yoga & Wellness Retreat",
        "category": "sports",
        "date": "May 21, 2024",
        "time": "8:00 AM - 12:00 PM",
        "location": "Wellness Center",
        "description": "Morning yoga session, meditation workshop, and wellness seminar.",
        "capacity": 60,
        "registered": 45,
        "speaker": "Certified Yoga Instructor",
        "tags": ["Yoga", "Wellness", "Mental Health"],
        "price": "Free"
    },
    {
        "id": 10,
        "name": "Hackathon 2024",
        "category": "technical",
        "date": "May 24-26, 2024",
        "time": "48-hour event",
        "location": "Innovation Hub",
        "description": "48-hour coding competition with $5000 in prizes.",
        "capacity": 200,
        "registered": 156,
        "speaker": "Tech Mentors",
        "tags": ["Hackathon", "Coding", "Innovation"],
        "price": "Free"
    }
]

# User sessions storage (in-memory, replace with database in production)
user_sessions = {}

# Interest keywords mapping
INTEREST_MAP = {
    "technical": ["coding", "programming", "ai", "machine learning", "hackathon", "python", "tech", "software", "developer", "computer", "data science"],
    "career": ["job", "internship", "career", "placement", "recruitment", "company", "interview", "resume", "networking", "salary", "employment"],
    "cultural": ["cultural", "festival", "music", "dance", "art", "performance", "celebration", "traditional", "food", "concert", "show"],
    "sports": ["sports", "basketball", "tournament", "fitness", "yoga", "game", "athletics", "competition", "wellness", "exercise", "workout"],
    "academic": ["research", "symposium", "academic", "study", "paper", "conference", "seminar", "workshop", "presentation", "thesis"]
}

def detect_interest(message):
    """Detect user interest from message"""
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
    """Generate response based on message"""
    msg_lower = message.lower()
    
    # Help command
    if any(word in msg_lower for word in ["help", "commands", "what can you do"]):
        return {
            "response": "Available Commands:\n\n"
                       "📌 Find Events:\n"
                       "• 'Show technical events' - Coding, AI, workshops\n"
                       "• 'Show career events' - Jobs, internships\n"
                       "• 'Show cultural events' - Festivals, music\n"
                       "• 'Show sports events' - Tournaments, fitness\n"
                       "• 'Show academic events' - Research, symposiums\n\n"
                       "🔍 Browse:\n"
                       "• 'Upcoming events' - Events happening soon\n"
                       "• 'Trending events' - Most popular events\n"
                       "• 'All events' - List all events\n\n"
                       "📝 Register:\n"
                       "• 'Register for event 5' - Register for specific event\n\n"
                       "ℹ️ Details:\n"
                       "• 'Tell me about AI workshop' - Get event details",
            "intent": "help"
        }
    
    # Register for event
    if "register" in msg_lower:
        numbers = re.findall(r'\d+', message)
        if numbers:
            event_id = int(numbers[0])
            # Try database registration first
            student_id = 1  # Replace with actual student ID from session
            success, result = register_student_for_event_db(event_id, student_id)
            
            if success:
                return {
                    "response": result,
                    "intent": "registration"
                }
            else:
                # Fallback to in-memory registration
                event = next((e for e in EVENTS if e['id'] == event_id), None)
                if event:
                    if event['registered'] < event['capacity']:
                        event['registered'] += 1
                        return {
                            "response": f"✅ Successfully registered for {event['name']}!",
                            "event": event,
                            "intent": "registration"
                        }
                    else:
                        return {
                            "response": f"❌ Sorry, {event['name']} is full!",
                            "intent": "registration_failed"
                        }
                else:
                    return {
                        "response": f"❌ Event with ID {event_id} not found. Available IDs: {', '.join([str(e['id']) for e in EVENTS])}",
                        "intent": "registration_failed"
                    }
        else:
            return {
                "response": "Please specify event ID. Example: 'Register for event 5'",
                "intent": "registration_help"
            }
    
    # Get specific event details - Try database first
    db_events = get_events_from_db()
    if db_events:
        for event in db_events:
            if event.get('title', '').lower() in msg_lower:
                return {
                    "response": event,
                    "intent": "event_details"
                }
    else:
        # Fallback to in-memory events
        for event in EVENTS:
            if event['name'].lower() in msg_lower:
                return {
                    "response": event,
                    "intent": "event_details"
                }
    
    # Upcoming events - Try database first
    if any(word in msg_lower for word in ["upcoming", "this week", "soon"]):
        db_upcoming = get_upcoming_events_from_db(30)
        if db_upcoming:
            return {
                "response": db_upcoming,
                "intent": "upcoming_events",
                "count": len(db_upcoming)
            }
        else:
            upcoming = EVENTS[:5]
            return {
                "response": upcoming,
                "intent": "upcoming_events",
                "count": len(upcoming)
            }
    
    # Trending events - Try database first
    if any(word in msg_lower for word in ["trending", "popular", "hot"]):
        db_trending = get_trending_events_from_db(3)
        if db_trending:
            return {
                "response": db_trending,
                "intent": "trending_events"
            }
        else:
            trending = sorted(EVENTS, key=lambda x: x['registered']/x['capacity'], reverse=True)[:3]
            return {
                "response": trending,
                "intent": "trending_events"
            }
    
    # All events - Try database first
    if "all events" in msg_lower or "list all" in msg_lower:
        db_all = get_events_from_db()
        if db_all:
            return {
                "response": db_all,
                "intent": "all_events",
                "count": len(db_all)
            }
        else:
            return {
                "response": EVENTS,
                "intent": "all_events",
                "count": len(EVENTS)
            }
    
    # Category-based queries - Try database first
    categories = {
        "technical": ["technical", "coding", "programming", "ai", "hackathon"],
        "career": ["career", "job", "internship", "placement"],
        "cultural": ["cultural", "festival", "music", "dance", "art"],
        "sports": ["sports", "basketball", "tournament", "fitness", "yoga"],
        "academic": ["academic", "research", "symposium", "study"]
    }
    
    for category, keywords in categories.items():
        if any(keyword in msg_lower for keyword in keywords):
            db_filtered = get_events_from_db(category=category)
            if db_filtered:
                return {
                    "response": db_filtered,
                    "intent": f"{category}_events",
                    "category": category,
                    "count": len(db_filtered)
                }
            else:
                filtered = [e for e in EVENTS if e['category'] == category]
                return {
                    "response": filtered,
                    "intent": f"{category}_events",
                    "category": category,
                    "count": len(filtered)
                }
    
    # Interest-based detection
    interest = detect_interest(message)
    if interest:
        db_interest = get_events_from_db(category=interest)
        if db_interest:
            return {
                "response": db_interest,
                "intent": "recommended_events",
                "interest": interest,
                "count": len(db_interest)
            }
        else:
            filtered = [e for e in EVENTS if e['category'] == interest]
            if filtered:
                return {
                    "response": filtered,
                    "intent": "recommended_events",
                    "interest": interest,
                    "count": len(filtered)
                }
    
    # Default greeting
    if any(word in msg_lower for word in ["hello", "hi", "hey"]):
        return {
            "response": "Hello! I'm your University Event Assistant. Type 'help' to see what I can do!",
            "intent": "greeting"
        }
    
    # Default response
    return {
        "response": "I'm not sure about that. Type 'help' to see all commands or tell me what events you're interested in!",
        "intent": "unknown"
    }

# ============= API ENDPOINTS =============

@app.route('/api/chat', methods=['POST'])
def chat():
    """Main chat endpoint"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No JSON data provided'
            }), 400
        
        message = data.get('message', '').strip()
        user_id = data.get('user_id', None)
        
        if not message:
            return jsonify({
                'success': False,
                'error': 'Message is required'
            }), 400
        
        # Generate response
        result = generate_response(message, user_id)
        
        return jsonify({
            'success': True,
            'message': message,
            **result
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/events', methods=['GET'])
def get_events():
    """Get events with filters"""
    try:
        category = request.args.get('category')
        event_id = request.args.get('id')
        
        if event_id:
            # Try database first
            db_event = get_events_from_db(event_id=int(event_id))
            if db_event:
                return jsonify({
                    'success': True,
                    'event': db_event
                })
            
            # Fallback to in-memory
            event = next((e for e in EVENTS if e['id'] == int(event_id)), None)
            if event:
                return jsonify({
                    'success': True,
                    'event': event
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Event not found'
                }), 404
        
        if category:
            # Try database first
            db_filtered = get_events_from_db(category=category)
            if db_filtered:
                return jsonify({
                    'success': True,
                    'events': db_filtered,
                    'count': len(db_filtered),
                    'category': category,
                    'source': 'database'
                })
            
            # Fallback to in-memory
            filtered = [e for e in EVENTS if e['category'].lower() == category.lower()]
            return jsonify({
                'success': True,
                'events': filtered,
                'count': len(filtered),
                'category': category,
                'source': 'memory'
            })
        
        # Try database first for all events
        db_events = get_events_from_db()
        if db_events:
            return jsonify({
                'success': True,
                'events': db_events,
                'count': len(db_events),
                'source': 'database'
            })
        
        # Return all events from memory
        return jsonify({
            'success': True,
            'events': EVENTS,
            'count': len(EVENTS),
            'source': 'memory'
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/events/<int:event_id>', methods=['GET'])
def get_event_by_id(event_id):
    """Get single event by ID"""
    try:
        # Try database first
        db_event = get_events_from_db(event_id=event_id)
        if db_event:
            return jsonify({
                'success': True,
                'event': db_event,
                'source': 'database'
            })
        
        # Fallback to in-memory
        event = next((e for e in EVENTS if e['id'] == event_id), None)
        if event:
            return jsonify({
                'success': True,
                'event': event,
                'source': 'memory'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Event not found'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/events/<int:event_id>/register', methods=['POST'])
def register_for_event(event_id):
    """Register for an event"""
    try:
        data = request.get_json()
        user_id = data.get('user_id') if data else None
        student_id = data.get('student_id', 1)  # Default to 1 for testing
        
        # Try database registration first
        success, message = register_student_for_event_db(event_id, student_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'source': 'database'
            })
        
        # Fallback to in-memory registration
        event = next((e for e in EVENTS if e['id'] == event_id), None)
        
        if not event:
            return jsonify({
                'success': False,
                'error': 'Event not found'
            }), 404
        
        if event['registered'] >= event['capacity']:
            return jsonify({
                'success': False,
                'error': f'Sorry, {event["name"]} is full',
                'event': event
            }), 400
        
        # Register user
        event['registered'] += 1
        
        return jsonify({
            'success': True,
            'message': f'Successfully registered for {event["name"]}',
            'event': event,
            'user_id': user_id,
            'source': 'memory'
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/categories', methods=['GET'])
def get_categories():
    """Get all event categories"""
    # Try database first
    db_categories = get_event_categories_from_db()
    if db_categories:
        return jsonify({
            'success': True,
            'categories': [c['name'] for c in db_categories],
            'source': 'database'
        })
    
    # Fallback to in-memory
    categories = list(set([e['category'] for e in EVENTS]))
    return jsonify({
        'success': True,
        'categories': categories,
        'source': 'memory'
    })

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get API statistics"""
    # Try database first
    db_stats = get_db_stats()
    if db_stats:
        return jsonify({
            'success': True,
            'stats': db_stats,
            'source': 'database'
        })
    
    # Fallback to in-memory
    total_events = len(EVENTS)
    total_registrations = sum(e['registered'] for e in EVENTS)
    total_capacity = sum(e['capacity'] for e in EVENTS)
    
    return jsonify({
        'success': True,
        'stats': {
            'total_events': total_events,
            'total_registrations': total_registrations,
            'total_capacity': total_capacity,
            'average_fill_rate': round((total_registrations / total_capacity) * 100, 2)
        },
        'source': 'memory'
    })

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    # Check database connection
    db_status = "connected" if get_db_connection() else "disconnected"
    
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'events_count': len(EVENTS),
        'version': '1.0.0',
        'database': db_status
    })

@app.route('/', methods=['GET'])
def root():
    """Root endpoint with API info"""
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
        },
        'documentation': 'https://github.com/your-username/university-chatbot-backend'
    })

@app.errorhandler(404)
def not_found(e):
    return jsonify({
        'success': False,
        'error': 'Endpoint not found'
    }), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
