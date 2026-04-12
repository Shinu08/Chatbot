from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import re
from datetime import datetime
import mysql.connector
from mysql.connector import Error
import logging
import os
from flask import Flask, jsonify
from flask_cors import CORS
import pymysql
from pymysql import Error

app = Flask(__name__)
CORS(app)

# Database configuration
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'metro.proxy.rlwy.net'),
    'database': os.environ.get('DB_NAME', 'evently_db'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', 'rCcksrvhZVAYgbmXLQujAFYEjSSrXziw'),
    'port': int(os.environ.get('DB_PORT', 13782))
}

def get_db_connection():
    try:
        connection = pymysql.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],
            connect_timeout=30,
            cursorclass=pymysql.cursors.DictCursor
        )
        return connection
    except Error as e:
        print(f"Connection error: {e}")
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

# ============= ADMIN API ENDPOINTS FOR MANUAL DATA ENTRY =============

@app.route('/api/admin/categories/create', methods=['POST'])
def create_category():
    """Manually create an event category"""
    try:
        data = request.get_json()
        
        # Required fields
        name = data.get('name')
        slug = data.get('slug')
        
        if not name or not slug:
            return jsonify({'success': False, 'error': 'Name and slug are required'}), 400
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        
        # Insert category
        cursor.execute("""
            INSERT INTO event_categories (name, slug, is_active, created_at, updated_at)
            VALUES (%s, %s, 1, NOW(), NOW())
        """, (name, slug))
        
        connection.commit()
        category_id = cursor.lastrowid
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': f'Category "{name}" created successfully',
            'category_id': category_id
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/events/create', methods=['POST'])
def create_event():
    """Manually create an event"""
    try:
        data = request.get_json()
        
        # Required fields
        required_fields = ['title', 'description', 'event_category_id', 'start_datetime', 
                          'end_datetime', 'venue', 'mode']
        
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'Missing required field: {field}'}), 400
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        
        # Generate slug from title
        slug = data['title'].lower().replace(' ', '-').replace('&', 'and').replace(',', '').replace('.', '')
        
        # Insert event
        cursor.execute("""
            INSERT INTO events (
                title, slug, description, event_category_id, created_by, organizer_type, 
                organizer_id, start_datetime, end_datetime, venue, mode, meeting_link, 
                max_participants, registration_deadline, banner_image, is_featured, 
                visibility, status, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """, (
            data['title'],
            slug,
            data['description'],
            data['event_category_id'],
            data.get('created_by', 'admin'),
            data.get('organizer_type', 'admin'),
            data.get('organizer_id', 1),
            data['start_datetime'],
            data['end_datetime'],
            data['venue'],
            data['mode'],
            data.get('meeting_link'),
            data.get('max_participants'),
            data.get('registration_deadline'),
            data.get('banner_image'),
            data.get('is_featured', 0),
            data.get('visibility', 'public'),
            'approved'  # Auto-approve for manual entries
        ))
        
        connection.commit()
        event_id = cursor.lastrowid
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': f'Event "{data["title"]}" created successfully',
            'event_id': event_id,
            'slug': slug
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/categories', methods=['GET'])
def list_categories():
    """List all categories (for reference)"""
    connection = get_db_connection()
    if not connection:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT id, name, slug, is_active FROM event_categories ORDER BY id")
        categories = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'categories': categories
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/seed-events', methods=['POST'])
def seed_default_events():
    """Seed the database with default events from your SQL file"""
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        
        # First, check if categories exist, if not, create them
        cursor.execute("SELECT COUNT(*) as count FROM event_categories")
        result = cursor.fetchone()
        
        if result[0] == 0:
            # Insert default categories
            default_categories = [
                (1, 'Entertainment', 'entertainment', 1),
                (2, 'Career & Learning', 'career-learning', 1),
                (3, 'Arts & Creativity', 'arts-creativity', 1),
                (4, 'Health & Wellness', 'health-wellness', 1),
                (5, 'Technology', 'technology', 1),
                (6, 'Sports', 'sports', 1),
                (7, 'Travel & Lifestyle', 'travel-lifestyle', 1)
            ]
            
            cursor.executemany("""
                INSERT INTO event_categories (id, name, slug, is_active, created_at, updated_at)
                VALUES (%s, %s, %s, %s, NOW(), NOW())
            """, default_categories)
            print("✅ Default categories inserted")
        
        # Insert default events
        default_events = [
            (1, 'Plantation Programme', 'plantation-programme', 'Planting Trees in nearby areas', 4, 
             'admin', 'admin', 1, '2026-03-31 06:00:00', '2026-03-31 10:00:00', 
             'RPJ College', 'offline', None, 250, '2026-03-30 18:50:00', 
             'event_banners/KxLelilbP9fzaQ0AGIgDmhHwDY9sPe9wOE1cb3ue.webp', 1, 'public', 'approved'),
            
            (2, 'Internship & Training Programme', 'internship-training-progrmme', 
             'Internship & Training Opportunity to all the students', 2, 
             'admin', 'admin', 1, '2026-04-01 12:00:00', '2026-06-30 02:00:00', 
             'RPJ College - Online Mode', 'online', 'https://randomdailyurls.com/', 150, 
             '2026-03-31 06:00:00', 'event_banners/6lCpka2YLLoosWOUTl3s5gd1K5TpnYzx6Mc5l0AO.jpg', 
             1, 'public', 'approved'),
            
            (3, 'Sports Day Event', 'sports-day-event', 'Sports Day Organized in JK University', 6,
             'admin', 'admin', 1, '2026-04-15 09:00:00', '2026-04-15 03:00:00',
             'JK Sports Ground', 'offline', None, 800, '2026-04-01 06:00:00',
             'event_banners/Qs7BHFzYidUwlgD0mydfsxUpox5qCk1XkZ5kdg4z.jpg', 1, 'public', 'approved'),
            
            (4, 'Arts Festival 2026', 'arts-festival-2026', 'Arts Competition organized in our college', 3,
             'admin', 'admin', 1, '2026-04-25 03:00:00', '2026-04-25 04:30:00',
             'Indus University , Auditorium Hall', 'offline', None, 90, '2026-04-06 05:00:00',
             'event_banners/PeU4uUnVnUjpllaLeL4WM0yntXwSlQEVlygHnQ6a.jpg', 1, 'public', 'approved')
        ]
        
        for event in default_events:
            # Check if event already exists
            cursor.execute("SELECT id FROM events WHERE id = %s", (event[0],))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO events (
                        id, title, slug, description, event_category_id, created_by, organizer_type,
                        organizer_id, start_datetime, end_datetime, venue, mode, meeting_link,
                        max_participants, registration_deadline, banner_image, is_featured,
                        visibility, status, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                """, event + ('approved',))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Default events and categories seeded successfully!',
            'events_added': len(default_events)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

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

@app.route('/debug/env', methods=['GET'])
def debug_env():
    return jsonify({
        'DB_HOST': os.environ.get('DB_HOST'),
        'DB_PORT': os.environ.get('DB_PORT'),
        'DB_USER': os.environ.get('DB_USER'),
        'DB_PASSWORD': '***' + os.environ.get('DB_PASSWORD', '')[-4:] if os.environ.get('DB_PASSWORD') else None,
        'DB_NAME': os.environ.get('DB_NAME')
    })
    
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
