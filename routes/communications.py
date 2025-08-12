"""
WealthPro CRM - Communication Management Routes
FILE 7 of 8 - Upload this as routes/communications.py
"""

import logging
from datetime import datetime
from flask import Blueprint, render_template_string, request, redirect, url_for, session
from google.oauth2.credentials import Credentials
from models.google_drive import SimpleGoogleDrive

# Configure logging
logger = logging.getLogger(__name__)

# Create blueprint for communication routes
communications_bp = Blueprint('communications', __name__)

@communications_bp.route('/clients/<client_id>/communications', methods=['GET', 'POST'])
def client_communications(client_id):
    """Enhanced communications page with Google Drive integration and time tracking"""
    if 'credentials' not in session:
        return redirect(url_for('auth.authorize'))

    try:
        credentials = Credentials(**session['credentials'])
        drive = SimpleGoogleDrive(credentials)
        
        clients = drive.get_clients_enhanced()
        client = next((c for c in clients if c['client_id'] == client_id), None)
        if not client:
            return "Client not found", 404

        if request.method == 'POST':
            comm_data = {
                'communication_id': f"COM{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'client_id': client_id,
                'date': request.form.get('date', datetime.now().strftime('%Y-%m-%d')),
                'time': request.form.get('time', ''),
                'type': request.form.get('type', ''),
                'subject': request.form.get('subject', ''),
                'details': request.form.get('details', ''),
                'outcome': request.form.get('outcome', ''),
                'duration': request.form.get('duration', ''),
                'follow_up_required': request.form.get('follow_up_required', 'No'),
                'follow_up_date': request.form.get('follow_up_date', ''),
                'created_by': 'System User'
            }

            success = drive.add_communication_enhanced(comm_data, client)
            if success:
                return redirect(url_for('communications.client_communications', client_id=client_id))

        communications = drive.get_client_communications(client_id)
        
        return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM - Enhanced Communications</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { font-family: "Inter", sans-serif; }
        .gradient-wealth { background: linear-gradient(135deg, #1a365d 0%, #2563eb 100%); }
    </style>
</head>
<body class="bg-gray-50">
    <nav class="gradient-wealth text-white shadow-lg">
        <div class="max-w-7xl mx-auto px-6">
            <div class="flex justify-between items-center h-16">
                <h1 class="text-xl font-bold">WealthPro CRM</h1>
                <div class="flex items-center space-x-6">
                    <a href="/" class="hover:text-blue-200">Dashboard</a>
                    <a href="/clients" class="hover:text-blue-200">Clients</a>
                    <a href="/factfind" class="hover:text-blue-200">Fact Find</a>
                    <a href="/tasks" class="hover:text-blue-200">Tasks</a>
                </div>
            </div>
        </div>
    </nav>

    <main class="max-w-6xl mx-auto px-6 py-8">
        <div class="mb-8">
            <h1 class="text-3xl font-bold">Enhanced Communications: {{ client.display_name }}</h1>
            <p class="text-gray-600 mt-2">Track all interactions with time logging - saves to Google Drive</p>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <!-- Add New Communication Form -->
            <div class="lg:col-span-1">
                <div class="bg-white rounded-lg shadow p-6">
                    <h3 class="text-lg font-semibold mb-4">Add Communication</h3>
                    <form method="POST" class="space-y-4">
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">Date *</label>
                                <input type="date" name="date" value="{{ datetime.now().strftime('%Y-%m-%d') }}" required class="w-full px-3 py-2 border border-gray-300 rounded-md">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">Time *</label>
                                <input type="time" name="time" required class="w-full px-3 py-2 border border-gray-300 rounded-md">
                            </div>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Type *</label>
                            <select name="type" required class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                <option value="">Select...</option>
                                <option value="Phone Call">Phone Call</option>
                                <option value="Email">Email</option>
                                <option value="Meeting">Meeting</option>
                                <option value="Video Call">Video Call</option>
                                <option value="Letter">Letter</option>
                                <option value="Text Message">Text Message</option>
                                <option value="Other">Other</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Duration *</label>
                            <input type="text" name="duration" placeholder="e.g., 15 minutes, 1 hour" required class="w-full px-3 py-2 border border-gray-300 rounded-md">
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Subject</label>
                            <input type="text" name="subject" placeholder="Brief summary of topic" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Details</label>
                            <textarea name="details" rows="4" placeholder="What was discussed?" class="w-full px-3 py-2 border border-gray-300 rounded-md"></textarea>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Outcome</label>
                            <textarea name="outcome" rows="2" placeholder="What was the result?" class="w-full px-3 py-2 border border-gray-300 rounded-md"></textarea>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Follow Up Required?</label>
                            <select name="follow_up_required" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                <option value="No">No</option>
                                <option value="Yes">Yes</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Follow Up Date</label>
                            <input type="date" name="follow_up_date" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                        </div>
                        
                        <div class="bg-blue-50 p-3 rounded">
                            <p class="text-xs text-blue-700">💾 Saves to Google Drive: {{ client.display_name }}/Communications/</p>
                        </div>
                        
                        <button type="submit" class="w-full bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">
                            Add Communication
                        </button>
                    </form>
                </div>
            </div>

            <!-- Communications History -->
            <div class="lg:col-span-2">
                <div class="bg-white rounded-lg shadow">
                    <div class="p-6 border-b">
                        <h3 class="text-lg font-semibold">Communication History</h3>
                    </div>
                    <div class="p-6">
                        {% if communications %}
                            <div class="space-y-4">
                                {% for comm in communications %}
                                <div class="border-l-4 {% if comm.type == 'Meeting' %}border-blue-500{% elif comm.type == 'Phone Call' %}border-green-500{% elif comm.type == 'Email' %}border-purple-500{% else %}border-gray-500{% endif %} pl-4 py-3 bg-gray-50 rounded-r">
                                    <div class="flex justify-between items-start">
                                        <div class="flex-1">
                                            <h4 class="font-semibold text-gray-900">{{ comm.subject or 'No Subject' }}</h4>
                                            <p class="text-sm text-gray-600">{{ comm.type }} - {{ comm.date }}{% if comm.time %} at {{ comm.time }}{% endif %}</p>
                                            {% if comm.duration %}
                                            <p class="text-xs text-gray-500">Duration: {{ comm.duration }}</p>
                                            {% endif %}
                                        </div>
                                        {% if comm.follow_up_required == 'Yes' %}
                                        <span class="bg-yellow-100 text-yellow-800 text-xs px-2 py-1 rounded">Follow Up: {{ comm.follow_up_date or 'TBD' }}</span>
                                        {% endif %}
                                    </div>
                                    {% if comm.details %}
                                    <div class="mt-2 text-sm text-gray-700">
                                        <strong>Details:</strong> {{ comm.details }}
                                    </div>
                                    {% endif %}
                                    {% if comm.outcome %}
                                    <div class="mt-1 text-sm text-gray-600">
                                        <strong>Outcome:</strong> {{ comm.outcome }}
                                    </div>
                                    {% endif %}
                                </div>
                                {% endfor %}
                            </div>
                        {% else %}
                            <p class="text-gray-500 text-center py-8">No communications recorded yet.</p>
                        {% endif %}
                    </div>
                </div>
            </div>
        </div>

        <div class="mt-8">
            <a href="/clients/{{ client.client_id }}/profile" class="bg-gray-600 text-white px-6 py-3 rounded-lg hover:bg-gray-700">
                Back to Profile
            </a>
        </div>
    </main>
</body>
</html>
        ''', client=client, communications=communications, datetime=datetime)

    except Exception as e:
        logger.error(f"Enhanced communications error: {e}")
        return f"Error: {e}", 500

@communications_bp.route('/communications/summary')
def communications_summary():
    """Overview of all recent communications across all clients"""
    if 'credentials' not in session:
        return redirect(url_for('auth.authorize'))

    try:
        credentials = Credentials(**session['credentials'])
        drive = SimpleGoogleDrive(credentials)
        clients = drive.get_clients_enhanced()
        
        # Get recent communications from all clients
        all_communications = []
        client_lookup = {c['client_id']: c['display_name'] for c in clients}
        
        for client in clients:
            client_comms = drive.get_client_communications(client['client_id'])
            for comm in client_comms[:5]:  # Last 5 per client
                comm['client_name'] = client['display_name']
                all_communications.append(comm)
        
        # Sort by date, most recent first
        all_communications.sort(key=lambda x: x['date'], reverse=True)
        recent_communications = all_communications[:20]  # Top 20 most recent

        return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM - Communications Summary</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { font-family: "Inter", sans-serif; }
        .gradient-wealth { background: linear-gradient(135deg, #1a365d 0%, #2563eb 100%); }
    </style>
</head>
<body class="bg-gray-50">
    <nav class="gradient-wealth text-white shadow-lg">
        <div class="max-w-7xl mx-auto px-6">
            <div class="flex justify-between items-center h-16">
                <h1 class="text-xl font-bold">WealthPro CRM</h1>
                <div class="flex items-center space-x-6">
                    <a href="/" class="hover:text-blue-200">Dashboard</a>
                    <a href="/clients" class="hover:text-blue-200">Clients</a>
                    <a href="/factfind" class="hover:text-blue-200">Fact Find</a>
                    <a href="/tasks" class="hover:text-blue-200">Tasks</a>
                </div>
            </div>
        </div>
    </nav>

    <main class="max-w-7xl mx-auto px-6 py-8">
        <div class="mb-8">
            <h1 class="text-3xl font-bold">Recent Communications</h1>
            <p class="text-gray-600 mt-2">Overview of recent client interactions across all clients</p>
        </div>

        <div class="bg-white rounded-lg shadow">
            <div class="p-6 border-b">
                <h3 class="text-lg font-semibold">Latest 20 Communications</h3>
            </div>
            <div class="p-6">
                {% if recent_communications %}
                    <div class="space-y-4">
                        {% for comm in recent_communications %}
                        <div class="border-l-4 {% if comm.type == 'Meeting' %}border-blue-500{% elif comm.type == 'Phone Call' %}border-green-500{% elif comm.type == 'Email' %}border-purple-500{% else %}border-gray-500{% endif %} pl-4 py-3 bg-gray-50 rounded-r">
                            <div class="flex justify-between items-start">
                                <div class="flex-1">
                                    <h4 class="font-semibold text-gray-900">{{ comm.subject or 'No Subject' }}</h4>
                                    <p class="text-sm text-gray-600">{{ comm.client_name }} | {{ comm.type }} - {{ comm.date }}</p>
                                    {% if comm.details %}
                                    <p class="text-sm text-gray-700 mt-1">{{ comm.details[:100] }}{% if comm.details|length > 100 %}...{% endif %}</p>
                                    {% endif %}
                                </div>
                                {% if comm.follow_up_required == 'Yes' %}
                                <span class="bg-yellow-100 text-yellow-800 text-xs px-2 py-1 rounded">Follow Up Required</span>
                                {% endif %}
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                {% else %}
                    <p class="text-gray-500 text-center py-8">No communications recorded yet.</p>
                {% endif %}
            </div>
        </div>
    </main>
</body>
</html>
        ''', recent_communications=recent_communications)

    except Exception as e:
        logger.error(f"Communications summary error: {e}")
        return f"Error: {e}", 500
