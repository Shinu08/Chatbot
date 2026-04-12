from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import re
from datetime import datetime
import mysql.connector
from mysql.connector import Error
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False
CORS(app)  # Enable CORS for all routes

# ============= DATABASE CONFIGURATION =============
# These will be set as Environment Variables in Render
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', ''),
    'database': os.environ.get('DB_NAME', 'railway'),
    'user': os.environ.get('DB_USER', ''),
    'password': os.environ.get('DB_PASSWORD', ''),
    'port': int(os.environ.get('DB_PORT', 3306))
}

def get_db_connection():
    """Create database connection for Railway MySQL from Render"""
    try:
        # Validate config
        if not DB_CONFIG['host'] or not DB_CONFIG['user']:
            logger.error("Database configuration incomplete")
            return None
            
        logger.info(f"Connecting to: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
        logger.info(f"Database: {DB_CONFIG['database']}")
        
        connection = mysql.connector.connect(
            host=DB_CONFIG['host'],
            database=DB_CONFIG['database'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            port=DB_CONFIG['port'],
            connect_timeout=30,
            use_pure=True
        )
        
        if connection.is_connected():
            logger.info("✅ Connected to Railway MySQL database")
        return connection
        
    except Error as e:
        logger.error(f"Database connection error: {e}")
        return None

# ============= EVENT FUNCTIONS =============
def get_events_from_db(category=None, event_id=None):
    """Fetch events from Railway MySQL database"""
    connection = get_db_connection()
    if not connection:
        logger.error("No database connection")
        return [] if not event_id else None
    
    try:
        cursor = connection.cursor(dictionary=True)
        
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
            
    except Error as err:
        logger.error(f"Database error: {err}")
        return [] if not event_id else None
    finally:
        if connection and connection.is_connected():
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
    """Register a student for an event"""
    connection = get_db_connection()
    if not connection:
        return False, "Database connection failed"
    
    try:
        cursor = connection.cursor(dictionary=True)
        
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
        
    except Error as err:
        logger.error(f"Database error: {err}")
        return False, f"Database error: {err}"
    finally:
        if connection and connection.is_connected():
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
        'database_host': DB_CONFIG['host']
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
        return jsonify({'success': True, 'categories': []})
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT name FROM event_categories WHERE is_active = 1")
        categories = [row['name'] for row in cursor.fetchall()]
        return jsonify({'success': True, 'categories': categories})
    except Error as err:
        logger.error(f"Error in get_categories: {err}")
        return jsonify({'success': False, 'error': str(err)}), 500
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get database statistics"""
    connection = get_db_connection()
    if not connection:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute("SELECT COUNT(*) as total FROM events WHERE status = 'approved'")
        total_events = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(*) as total FROM event_registrations")
        total_registrations = cursor.fetchone()['total']
        
        cursor.execute("SELECT SUM(max_participants) as total FROM events WHERE status = 'approved'")
        total_capacity = cursor.fetchone()['total'] or 0
        
        return jsonify({
            'success': True,
            'stats': {
                'total_events': total_events,
                'total_registrations': total_registrations,
                'total_capacity': total_capacity,
                'average_fill_rate': round((total_registrations / total_capacity) * 100, 2) if total_capacity > 0 else 0
            }
        })
    except Error as err:
        logger.error(f"Error in get_stats: {err}")
        return jsonify({'success': False, 'error': str(err)}), 500
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/api/chat', methods=['POST'])
def chat():
    """Chat endpoint for the chatbot"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400
        
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({'success': False, 'error': 'Message is required'}), 400
        
        # Simple response logic
        if "events" in message.lower():
            events = get_events_from_db()
            return jsonify({
                'success': True,
                'message': message,
                'response': events,
                'intent': 'all_events',
                'count': len(events)
            })
        
        return jsonify({
            'success': True,
            'message': message,
            'response': "I can help you find events! Try asking for 'all events' or specific categories like 'technical events'.",
            'intent': 'unknown'
        })
    except Exception as e:
        logger.error(f"Error in chat: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/', methods=['GET'])
def root():
    """Root endpoint with API information"""
    return jsonify({
        'name': 'University Event Chatbot API',
        'version': '1.0.0',
        'description': 'AI-powered event management chatbot for universities',
        'database_host': DB_CONFIG['host'],
        'endpoints': {
            'GET /health': 'Health check',
            'GET /api/events': 'Get all events',
            'GET /api/events?category=technical': 'Filter events by category',
            'GET /api/events/{id}': 'Get specific event',
            'POST /api/events/{id}/register': 'Register for event',
            'GET /api/categories': 'Get event categories',
            'GET /api/stats': 'Get statistics',
            'POST /api/chat': 'Chat with the bot'
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Starting Flask app on port {port}")
    print(f"📊 Database Host: {DB_CONFIG['host']}")
    print(f"📊 Database Name: {DB_CONFIG['database']}")
    app.run(host='0.0.0.0', port=port, debug=False)
