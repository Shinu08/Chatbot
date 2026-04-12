from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import re
from datetime import datetime
import pymysql
from pymysql import Error
import logging
import socket

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# ============= DATABASE CONFIGURATION =============
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'metro.proxy.rlwy.net'),
    'database': os.environ.get('DB_NAME', 'evently_db'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', 'rCcksrvhZVAYgbmXLQujAFYEjSSrXziw'),
    'port': int(os.environ.get('DB_PORT', 13782))
}

# ============= FALLBACK EVENT DATA (from evently_db(2).sql) =============
FALLBACK_EVENTS = [
    {
        "id": 1,
        "title": "Plantation Programme",
        "slug": "plantation-programme",
        "description": "Planting Trees in nearby areas",
        "category_id": 4,
        "category_name": "Health & Wellness",
        "frontend_category": "wellness",
        "start_datetime": "2026-03-31 06:00:00",
        "end_datetime": "2026-03-31 10:00:00",
        "venue": "RPJ College",
        "mode": "offline",
        "meeting_link": None,
        "max_participants": 250,
        "registered_count": 0,
        "created_by": "admin",
        "banner_image": "event_banners/KxLelilbP9fzaQ0AGIgDmhHwDY9sPe9wOE1cb3ue.webp",
        "is_featured": 1,
        "status": "approved"
    },
    {
        "id": 2,
        "title": "Internship & Training Programme",
        "slug": "internship-training-progrmme",
        "description": "Internship & Training Opportunity to all the students",
        "category_id": 2,
        "category_name": "Career & Learning",
        "frontend_category": "career",
        "start_datetime": "2026-04-01 12:00:00",
        "end_datetime": "2026-06-30 14:00:00",
        "venue": "RPJ College - Online Mode",
        "mode": "online",
        "meeting_link": "https://randomdailyurls.com/",
        "max_participants": 150,
        "registered_count": 1,
        "created_by": "admin",
        "banner_image": "event_banners/6lCpka2YLLoosWOUTl3s5gd1K5TpnYzx6Mc5l0AO.jpg",
        "is_featured": 1,
        "status": "approved"
    },
    {
        "id": 3,
        "title": "Sports Day Event",
        "slug": "sports-day-event",
        "description": "Sports Day Organized in JK University",
        "category_id": 6,
        "category_name": "Sports",
        "frontend_category": "sports",
        "start_datetime": "2026-04-15 09:00:00",
        "end_datetime": "2026-04-15 15:00:00",
        "venue": "JK Sports Ground",
        "mode": "offline",
        "meeting_link": None,
        "max_participants": 800,
        "registered_count": 1,
        "created_by": "admin",
        "banner_image": "event_banners/Qs7BHFzYidUwlgD0mydfsxUpox5qCk1XkZ5kdg4z.jpg",
        "is_featured": 1,
        "status": "approved"
    },
    {
        "id": 4,
        "title": "Arts Festival 2026",
        "slug": "arts-festival-2026",
        "description": "Arts Competition organized in our college",
        "category_id": 3,
        "category_name": "Arts & Creativity",
        "frontend_category": "academic",
        "start_datetime": "2026-04-25 15:00:00",
        "end_datetime": "2026-04-25 16:30:00",
        "venue": "Indus University, Auditorium Hall",
        "mode": "offline",
        "meeting_link": None,
        "max_participants": 90,
        "registered_count": 1,
        "created_by": "admin",
        "banner_image": "event_banners/PeU4uUnVnUjpllaLeL4WM0yntXwSlQEVlygHnQ6a.jpg",
        "is_featured": 1,
        "status": "approved"
    }
]

FALLBACK_CATEGORIES = [
    {"id": 1, "name": "Entertainment", "slug": "entertainment", "frontend": "cultural"},
    {"id": 2, "name": "Career & Learning", "slug": "career-learning", "frontend": "career"},
    {"id": 3, "name": "Arts & Creativity", "slug": "arts-creativity", "frontend": "academic"},
    {"id": 4, "name": "Health & Wellness", "slug": "health-wellness", "frontend": "wellness"},
    {"id": 5, "name": "Technology", "slug": "technology", "frontend": "technical"},
    {"id": 6, "name": "Sports", "slug": "sports", "frontend": "sports"},
    {"id": 7, "name": "Travel & Lifestyle", "slug": "travel-lifestyle", "frontend": "lifestyle"}
]

# ============= DATABASE CONNECTION FUNCTION =============
def get_db_connection():
    """Create database connection for Railway MySQL from Render"""
    try:
        print(f"Connecting to: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
        
        connection = pymysql.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],
            connect_timeout=60,
            read_timeout=60,
            write_timeout=60,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True
        )
        
        # Test the connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        
        print("✅ Connected to Railway MySQL database successfully!")
        return connection
        
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return None

# ============= FALLBACK FUNCTIONS =============
def get_fallback_events(category=None, event_id=None):
    """Get events from fallback data when database is unavailable"""
    if event_id:
        event = next((e for e in FALLBACK_EVENTS if e['id'] == event_id), None)
        if event:
            return format_fallback_event(event)
        return None
    
    if category:
        filtered = [e for e in FALLBACK_EVENTS if e['frontend_category'] == category]
        return [format_fallback_event(event) for event in filtered]
    
    return [format_fallback_event(event) for event in FALLBACK_EVENTS]

def format_fallback_event(event):
    """Format fallback event to match API response structure"""
    start_date = datetime.strptime(event['start_datetime'], "%Y-%m-%d %H:%M:%S")
    
    return {
        "id": event['id'],
        "name": event['title'],
        "category": event['frontend_category'],
        "date": start_date.strftime("%B %d, %Y"),
        "time": start_date.strftime("%I:%M %p"),
        "location": event['venue'],
        "description": event['description'],
        "capacity": event['max_participants'],
        "registered": event['registered_count'],
        "speaker": event.get('created_by', 'University Organizer'),
        "tags": [event['category_name'], event['mode']],
        "price": "Free" if event['mode'] == 'offline' else "Check website",
        "mode": event['mode'],
        "meeting_link": event.get('meeting_link'),
        "registration_deadline": None
    }

# ============= EVENT FUNCTIONS =============
def get_events_from_db(category=None, event_id=None):
    """Fetch events from database with fallback to local data"""
    connection = get_db_connection()
    
    # If database connection fails, use fallback data
    if not connection:
        print("⚠️ Using fallback event data (database unavailable)")
        return get_fallback_events(category, event_id)
    
    try:
        cursor = connection.cursor()
        
        if event_id:
            query = """
                SELECT e.*, ec.name as category_name,
                       (SELECT COUNT(*) FROM event_registrations WHERE event_id = e.id) as registered_count
                FROM events e
                JOIN event_categories ec ON e.event_category_id = ec.id
                WHERE e.id = %s AND e.status = 'approved'
            """
            cursor.execute(query, (event_id,))
            result = cursor.fetchone()
            if result:
                return format_event_for_api(result)
            return None
        
        elif category:
            category_map = {
                'technical': 'Technology',
                'career': 'Career & Learning',
                'cultural': 'Entertainment',
                'sports': 'Sports',
                'academic': 'Arts & Creativity',
                'wellness': 'Health & Wellness'
            }
            db_category = category_map.get(category, category)
            
            query = """
                SELECT e.*, ec.name as category_name,
                       (SELECT COUNT(*) FROM event_registrations WHERE event_id = e.id) as registered_count
                FROM events e
                JOIN event_categories ec ON e.event_category_id = ec.id
                WHERE ec.name = %s AND e.status = 'approved'
                ORDER BY e.start_datetime ASC
            """
            cursor.execute(query, (db_category,))
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
            
    except Exception as err:
        print(f"Database error: {err}")
        print("⚠️ Falling back to local event data")
        return get_fallback_events(category, event_id)
    finally:
        if connection:
            cursor.close()
            connection.close()

def format_event_for_api(db_event):
    """Convert database event format to API response format"""
    start_date = db_event['start_datetime']
    if isinstance(start_date, datetime):
        date_str = start_date.strftime("%B %d, %Y")
        time_str = start_date.strftime("%I:%M %p")
    else:
        date_str = str(start_date) if start_date else "Date TBA"
        time_str = "Time TBA"
    
    category_mapping = {
        'Technology': 'technical',
        'Career & Learning': 'career',
        'Entertainment': 'cultural',
        'Sports': 'sports',
        'Arts & Creativity': 'academic',
        'Health & Wellness': 'wellness',
        'Travel & Lifestyle': 'lifestyle'
    }
    
    category_name = db_event.get('category_name', 'Technology')
    frontend_category = category_mapping.get(category_name, 'technical')
    registered = db_event.get('registered_count', 0)
    
    return {
        "id": db_event['id'],
        "name": db_event['title'],
        "category": frontend_category,
        "date": date_str,
        "time": time_str,
        "location": db_event['venue'],
        "description": db_event['description'],
        "capacity": db_event['max_participants'] if db_event['max_participants'] else 999,
        "registered": registered,
        "speaker": db_event.get('created_by', 'University Organizer'),
        "tags": [category_name, db_event.get('mode', 'offline')],
        "price": "Free" if db_event.get('mode') == 'offline' else "Check website",
        "mode": db_event['mode'],
        "meeting_link": db_event.get('meeting_link'),
        "registration_deadline": db_event['registration_deadline'].strftime("%B %d, %Y") if db_event['registration_deadline'] else None
    }

def register_student_for_event_db(event_id, student_id):
    """Register a student for an event with fallback support"""
    connection = get_db_connection()
    
    # If no database connection, use fallback
    if not connection:
        print("⚠️ Database unavailable, checking fallback events for registration")
        event = next((e for e in FALLBACK_EVENTS if e['id'] == event_id), None)
        if event:
            if event['registered_count'] < event['max_participants']:
                event['registered_count'] += 1
                return True, f"✅ Successfully registered for {event['title']}! (Demo mode)"
            else:
                return False, f"Sorry, {event['title']} is full"
        return False, "Event not found"
    
    try:
        cursor = connection.cursor()
        
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
        
        cursor.execute("""
            SELECT id FROM event_registrations 
            WHERE event_id = %s AND student_id = %s
        """, (event_id, student_id))
        
        if cursor.fetchone():
            return False, "Already registered for this event"
        
        cursor.execute("SELECT COUNT(*) as count FROM event_registrations")
        count = cursor.fetchone()['count']
        reg_id = f"EVT-{str(count + 1).zfill(4)}"
        
        cursor.execute("""
            INSERT INTO event_registrations (event_id, student_id, reg_id, status, created_at, updated_at)
            VALUES (%s, %s, %s, 'approved', NOW(), NOW())
        """, (event_id, student_id, reg_id))
        
        connection.commit()
        return True, f"✅ Successfully registered for {event['title']}! Registration ID: {reg_id}"
        
    except Exception as err:
        print(f"Database error: {err}")
        return False, f"Database error: {err}"
    finally:
        if connection:
            cursor.close()
            connection.close()

# ============= API ENDPOINTS =============

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    connection = get_db_connection()
    db_status = "connected" if connection else "disconnected"
    if connection:
        connection.close()
    
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'database': db_status,
        'database_host': DB_CONFIG['host'],
        'database_name': DB_CONFIG['database']
    })

@app.route('/api/events', methods=['GET'])
def get_events():
    """Get events with optional category filter"""
    try:
        category = request.args.get('category')
        event_id = request.args.get('id')
        
        if event_id:
            event = get_events_from_db(event_id=int(event_id))
            if event:
                return jsonify({'success': True, 'event': event})
            return jsonify({'success': False, 'error': 'Event not found'}), 404
        
        if category:
            events = get_events_from_db(category=category)
            return jsonify({
                'success': True,
                'events': events,
                'count': len(events),
                'category': category
            })
        
        events = get_events_from_db()
        return jsonify({
            'success': True,
            'events': events,
            'count': len(events)
        })
    except Exception as e:
        logger.error(f"Error in get_events: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/events/<int:event_id>', methods=['GET'])
def get_event_by_id(event_id):
    """Get single event by ID"""
    try:
        event = get_events_from_db(event_id=event_id)
        if event:
            return jsonify({'success': True, 'event': event})
        return jsonify({'success': False, 'error': 'Event not found'}), 404
    except Exception as e:
        logger.error(f"Error in get_event_by_id: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/events/<int:event_id>/register', methods=['POST'])
def register_for_event(event_id):
    """Register for an event"""
    try:
        data = request.get_json() or {}
        student_id = data.get('student_id', 1)
        
        success, message = register_student_for_event_db(event_id, student_id)
        
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'error': message}), 400
    except Exception as e:
        logger.error(f"Error in register_for_event: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/categories', methods=['GET'])
def get_categories():
    """Get all event categories"""
    connection = get_db_connection()
    if not connection:
        # Return fallback categories
        return jsonify({'success': True, 'categories': [c['name'] for c in FALLBACK_CATEGORIES]})
    
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT name FROM event_categories WHERE is_active = 1")
        categories = [row['name'] for row in cursor.fetchall()]
        return jsonify({'success': True, 'categories': categories})
    except Exception as err:
        logger.error(f"Error in get_categories: {err}")
        return jsonify({'success': True, 'categories': [c['name'] for c in FALLBACK_CATEGORIES]})
    finally:
        if connection:
            cursor.close()
            connection.close()

@app.route('/api/status', methods=['GET'])
def api_status():
    """Show API status and data source"""
    connection = get_db_connection()
    db_available = connection is not None
    if connection:
        connection.close()
    
    return jsonify({
        'database_connected': db_available,
        'data_source': 'database' if db_available else 'fallback (local events)',
        'events_available': len(FALLBACK_EVENTS),
        'categories_available': len(FALLBACK_CATEGORIES),
        'events': [{'id': e['id'], 'name': e['title']} for e in FALLBACK_EVENTS]
    })

@app.route('/debug/env', methods=['GET'])
def debug_env():
    """Debug environment variables"""
    return jsonify({
        'DB_HOST': os.environ.get('DB_HOST'),
        'DB_PORT': os.environ.get('DB_PORT'),
        'DB_USER': os.environ.get('DB_USER'),
        'DB_PASSWORD': '***' + os.environ.get('DB_PASSWORD', '')[-4:] if os.environ.get('DB_PASSWORD') else None,
        'DB_NAME': os.environ.get('DB_NAME')
    })

@app.route('/api/diagnose', methods=['GET'])
def diagnose_connection():
    """Comprehensive database connection diagnosis"""
    results = {
        'config': {
            'host': DB_CONFIG['host'],
            'port': DB_CONFIG['port'],
            'database': DB_CONFIG['database'],
            'user': DB_CONFIG['user'],
        },
        'tests': {}
    }
    
    # Test DNS Resolution
    try:
        ip = socket.gethostbyname(DB_CONFIG['host'])
        results['tests']['dns_resolution'] = f"✅ SUCCESS - Resolved to {ip}"
    except Exception as e:
        results['tests']['dns_resolution'] = f"❌ FAILED - {str(e)}"
        return jsonify(results)
    
    # Test Port Connectivity
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        result = sock.connect_ex((DB_CONFIG['host'], DB_CONFIG['port']))
        sock.close()
        if result == 0:
            results['tests']['port_connectivity'] = f"✅ SUCCESS - Port {DB_CONFIG['port']} is open"
        else:
            results['tests']['port_connectivity'] = f"❌ FAILED - Error code: {result}"
    except Exception as e:
        results['tests']['port_connectivity'] = f"❌ FAILED - {str(e)}"
    
    return jsonify(results)

@app.route('/', methods=['GET'])
def root():
    """Root endpoint with API information"""
    return jsonify({
        'name': 'University Event Chatbot API',
        'version': '1.0.0',
        'description': 'AI-powered event management chatbot for universities',
        'database_host': DB_CONFIG['host'],
        'database_name': DB_CONFIG['database'],
        'endpoints': {
            'GET /': 'API Information',
            'GET /health': 'Health check',
            'GET /api/events': 'Get all events',
            'GET /api/events?category=technical': 'Filter events by category',
            'GET /api/events/{id}': 'Get specific event',
            'POST /api/events/{id}/register': 'Register for event',
            'GET /api/categories': 'Get event categories',
            'GET /api/status': 'API status and data source',
            'GET /debug/env': 'Debug environment variables',
            'GET /api/diagnose': 'Database connection diagnosis'
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Starting Flask app on port {port}")
    print(f"📊 Database Host: {DB_CONFIG['host']}")
    print(f"📊 Database Name: {DB_CONFIG['database']}")
    print(f"📋 Fallback events loaded: {len(FALLBACK_EVENTS)} events")
    app.run(host='0.0.0.0', port=port, debug=False)
