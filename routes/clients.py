"""
WealthPro CRM - Client Management Routes
(Updated to add a 'Review' button that creates the Review {YEAR} pack and a Task)
"""

import logging
from datetime import datetime
from flask import Blueprint, render_template_string, request, redirect, url_for, session
from google.oauth2.credentials import Credentials
from models.google_drive import SimpleGoogleDrive

logger = logging.getLogger(__name__)
clients_bp = Blueprint('clients', __name__)

@clients_bp.route('/clients')
def clients():
    if 'credentials' not in session:
        return redirect(url_for('auth.authorize'))

    try:
        credentials = Credentials(**session['credentials'])
        drive = SimpleGoogleDrive(credentials)
        clients = drive.get_clients_enhanced()

        return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM - Clients</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { font-family: "Inter", sans-serif; }
        .gradient-wealth { background: linear-gradient(135deg, #1a365d 0%, #2563eb 100%); }
        .btn { @apply inline-block px-3 py-1 rounded text-sm; }
    </style>
</head>
<body class="bg-gray-50">
    <nav class="gradient-wealth text-white shadow-lg">
        <div class="max-w-7xl mx-auto px-6">
            <div class="flex justify-between items-center h-16">
                <h1 class="text-xl font-bold">WealthPro CRM</h1>
                <div class="flex items-center space-x-6">
                    <a href="/" class="hover:text-blue-200">Dashboard</a>
                    <a href="/clients" class="text-white font-semibold">Clients</a>
                    <a href="/factfind" class="hover:text-blue-200">Fact Find</a>
                    <a href="/tasks" class="hover:text-blue-200">Tasks</a>
                </div>
            </div>
        </div>
    </nav>

    <main class="max-w-7xl mx-auto px-6 py-8">
        <div class="flex justify-between items-center mb-8">
            <div>
                <h1 class="text-3xl font-bold">Clients (Sorted by Surname)</h1>
                <p class="text-gray-600 mt-1">Total clients: {{ clients|length }}</p>
            </div>
            <a href="/clients/add" class="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700">
                Add New Client
            </a>
        </div>

        {% if request.args.get('msg') %}
        <div class="mb-6 p-4 bg-green-100 border border-green-300 text-green-800 rounded">
            {{ request.args.get('msg') }}
        </div>
        {% endif %}

        <div class="bg-white rounded-lg shadow overflow-hidden">
            <table class="min-w-full">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Client</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Contact</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Portfolio</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                    {% for client in clients %}
                    <tr>
                        <td class="px-6 py-4">
                            <div class="font-medium text-gray-900">{{ client.display_name }}</div>
                            <div class="text-sm text-gray-500">ID: {{ client.client_id }}</div>
                        </td>
                        <td class="px-6 py-4">
                            <div class="text-sm text-gray-900">{{ client.email or 'N/A' }}</div>
                            <div class="text-sm text-gray-500">{{ client.phone or 'N/A' }}</div>
                        </td>
                        <td class="px-6 py-4">
                            <span class="px-2 py-1 text-xs rounded-full {% if client.status == 'active' %}bg-green-100 text-green-800{% elif client.status == 'deceased' %}bg-gray-100 text-gray-800{% elif client.status == 'no_longer_client' %}bg-red-100 text-red-800{% else %}bg-yellow-100 text-yellow-800{% endif %}">
                                {{ client.status.replace('_', ' ').title() }}
                            </span>
                        </td>
                        <td class="px-6 py-4 text-sm">£{{ "{:,.0f}".format(client.portfolio_value) }}</td>
                        <td class="px-6 py-4">
                            <div class="flex gap-2 flex-wrap items-center">
                                {% if client.folder_id %}
                                <a href="{{ client.folder_url }}" target="_blank" class="text-blue-600 hover:text-blue-800 text-sm">📁 Folder</a>
                                {% endif %}
                                <a href="/clients/{{ client.client_id }}/profile" class="text-purple-600 hover:text-purple-800 text-sm">👤 Profile</a>
                                <a href="/clients/{{ client.client_id }}/add_task" class="text-indigo-600 hover:text-indigo-800 text-sm">📝 Add Task</a>
                                <a href="/factfind/{{ client.client_id }}" class="text-green-600 hover:text-green-800 text-sm">📋 Fact Find</a>
                                <a href="/clients/edit/{{ client.client_id }}" class="text-orange-600 hover:text-orange-800 text-sm">✏️ Edit</a>
                                <a href="/clients/delete/{{ client.client_id }}" onclick="return confirm('Are you sure you want to delete this client? This will move their folder to Google Drive trash.')" class="text-red-600 hover:text-red-800 text-sm">🗑️ Delete</a>
                                <a href="/clients/{{ client.client_id }}/review" class="text-teal-700 hover:text-teal-900 text-sm font-semibold">🔄 Review</a>
                            </div>
                        </td>
                    </tr>
                    {% else %}
                    <tr>
                        <td colspan="5" class="px-6 py-4 text-center text-gray-500">
                            No clients found. <a href="/clients/add" class="text-blue-600">Add your first client</a>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </main>
</body>
</html>
        ''', clients=clients)

    except Exception as e:
        logger.error(f"Clients error: {e}")
        return f"Error: {e}", 500

@clients_bp.route('/clients/add', methods=['GET', 'POST'])
def add_client():
    if 'credentials' not in session:
        return redirect(url_for('auth.authorize'))

    if request.method == 'POST':
        try:
            credentials = Credentials(**session['credentials'])
            drive = SimpleGoogleDrive(credentials)

            first_name = request.form.get('first_name', '').strip()
            surname = request.form.get('surname', '').strip()
            email = request.form.get('email', '').strip()
            phone = request.form.get('phone', '').strip()
            status = request.form.get('status', 'prospect')
            portfolio_value = request.form.get('portfolio_value', '0')
            notes = request.form.get('notes', '').strip()

            if not first_name or not surname:
                raise ValueError("First name and surname required")

            client_id = f"WP{datetime.now().strftime('%Y%m%d%H%M%S')}"
            display_name = f"{surname}, {first_name}"

            folder_info = drive.create_client_folder_enhanced(first_name, surname, status)
            if not folder_info:
                raise Exception("Failed to create folders")

            client_data = {
                'client_id': client_id,
                'display_name': display_name,
                'first_name': first_name,
                'surname': surname,
                'email': email,
                'phone': phone,
                'status': status,
                'date_added': datetime.now().strftime('%Y-%m-%d'),
                'folder_id': folder_info['client_folder_id'],
                'portfolio_value': float(portfolio_value) if portfolio_value else 0.0,
                'notes': notes
            }

            success = drive.add_client(client_data)
            if success:
                return redirect(url_for('clients.clients', msg="Client created successfully"))
            else:
                raise Exception("Failed to save client")

        except Exception as e:
            logger.error(f"Add client error: {e}")
            return f"Error adding client: {e}", 500

    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM - Add Client</title>
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

    <main class="max-w-4xl mx-auto px-6 py-8">
        <div class="mb-8">
            <h1 class="text-3xl font-bold">Add New Client</h1>
            <p class="text-gray-600 mt-2">Client will be filed as "Surname, First Name" in A–Z folder system</p>
        </div>

        <div class="bg-white rounded-lg shadow p-8">
            <form method="POST" class="space-y-6">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">First Name *</label>
                        <input type="text" name="first_name" required class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Surname *</label>
                        <input type="text" name="surname" required class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                        <p class="text-xs text-gray-500 mt-1">Will display as "Surname, First Name"</p>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Email</label>
                        <input type="email" name="email" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Phone</label>
                        <input type="tel" name="phone" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Status</label>
                        <select name="status" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                            <option value="prospect">Prospect</option>
                            <option value="active">Active Client</option>
                            <option value="no_longer_client">No Longer Client</option>
                            <option value="deceased">Deceased</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Portfolio Value (£)</label>
                        <input type="number" name="portfolio_value" step="0.01" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                    </div>
                </div>

                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Notes</label>
                    <textarea name="notes" rows="4" class="w-full px-3 py-2 border border-gray-300 rounded-md"></textarea>
                </div>

                <div class="bg-blue-50 p-4 rounded-lg">
                    <h3 class="text-sm font-medium text-blue-800 mb-2">📁 Enhanced Filing System</h3>
                    <p class="text-sm text-blue-700">Reviews (auto “Review {YEAR}” + templates), ID&V, FF & ATR, Research, LOAs, Suitability Letter, Meeting Notes, Terms of Business, Policy Information, Valuation, Tasks (Ongoing/Completed), Communications</p>
                </div>

                <div class="flex justify-between">
                    <a href="/clients" class="px-6 py-3 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">Cancel</a>
                    <button type="submit" class="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700">Create Client</button>
                </div>
            </form>
        </div>
    </main>
</body>
</html>
    ''')

@clients_bp.route('/clients/edit/<client_id>', methods=['GET', 'POST'])
def edit_client(client_id):
    if 'credentials' not in session:
        return redirect(url_for('auth.authorize'))

    try:
        credentials = Credentials(**session['credentials'])
        drive = SimpleGoogleDrive(credentials)

        if request.method == 'POST':
            new_status = request.form.get('status')
            success = drive.update_client_status(client_id, new_status)
            if success:
                return redirect(url_for('clients.clients', msg="Client status updated"))
            else:
                return f"Error updating client status", 500

        clients = drive.get_clients_enhanced()
        client = next((c for c in clients if c['client_id'] == client_id), None)
        if not client:
            return "Client not found", 404

        return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM - Edit Client</title>
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

    <main class="max-w-4xl mx-auto px-6 py-8">
        <div class="mb-8">
            <h1 class="text-3xl font-bold">Edit Client: {{ client.display_name }}</h1>
            <p class="text-gray-600 mt-2">Change client status and update records</p>
        </div>

        <div class="bg-white rounded-lg shadow p-8">
            <form method="POST" class="space-y-6">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Current Status</label>
                        <p class="text-lg font-semibold text-gray-900 capitalize">{{ client.status.replace('_', ' ') }}</p>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">New Status</label>
                        <select name="status" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                            <option value="prospect" {% if client.status == 'prospect' %}selected{% endif %}>Prospect</option>
                            <option value="active" {% if client.status == 'active' %}selected{% endif %}>Active Client</option>
                            <option value="no_longer_client" {% if client.status == 'no_longer_client' %}selected{% endif %}>No Longer Client</option>
                            <option value="deceased" {% if client.status == 'deceased' %}selected{% endif %}>Deceased</option>
                        </select>
                    </div>
                </div>

                <div class="bg-blue-50 p-4 rounded-lg">
                    <h3 class="text-sm font-medium text-blue-800 mb-2">📁 Folder Organization</h3>
                    <p class="text-sm text-blue-700">Changing status will move the client's Google Drive folder to the appropriate section.</p>
                </div>

                <div class="flex justify-between">
                    <a href="/clients" class="px-6 py-3 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">Cancel</a>
                    <button type="submit" class="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700">Update Client Status</button>
                </div>
            </form>
        </div>
    </main>
</body>
</html>
        ''', client=client)

    except Exception as e:
        logger.error(f"Edit client error: {e}")
        return f"Error: {e}", 500

@clients_bp.route('/clients/delete/<client_id>')
def delete_client(client_id):
    if 'credentials' not in session:
        return redirect(url_for('auth.authorize'))

    try:
        credentials = Credentials(**session['credentials'])
        drive = SimpleGoogleDrive(credentials)
        success = drive.delete_client(client_id)
        if success:
            return redirect(url_for('clients.clients', msg="Client deleted"))
        else:
            return f"Error deleting client", 500
    except Exception as e:
        logger.error(f"Delete client error: {e}")
        return f"Error: {e}", 500

@clients_bp.route('/clients/<client_id>/profile', methods=['GET', 'POST'])
def client_profile(client_id):
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
            profile_data = {
                'client_id': client_id,
                'address_line_1': request.form.get('address_line_1', ''),
                'address_line_2': request.form.get('address_line_2', ''),
                'city': request.form.get('city', ''),
                'county': request.form.get('county', ''),
                'postcode': request.form.get('postcode', ''),
                'country': request.form.get('country', 'UK'),
                'date_of_birth': request.form.get('date_of_birth', ''),
                'occupation': request.form.get('occupation', ''),
                'employer': request.form.get('employer', ''),
                'emergency_contact_name': request.form.get('emergency_contact_name', ''),
                'emergency_contact_phone': request.form.get('emergency_contact_phone', ''),
                'emergency_contact_relationship': request.form.get('emergency_contact_relationship', ''),
                'investment_goals': request.form.get('investment_goals', ''),
                'risk_profile': request.form.get('risk_profile', ''),
                'preferred_contact_method': request.form.get('preferred_contact_method', ''),
                'next_review_date': request.form.get('next_review_date', ''),
                'created_date': datetime.now().strftime('%Y-%m-%d'),
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            success = drive.update_client_profile(client_id, profile_data)
            if success:
                return redirect(url_for('clients.client_profile', client_id=client_id))

        profile = drive.get_client_profile(client_id)

        # Add a Review button on the profile too
        review_button_html = f'''
            <a href="/clients/{ client_id }/review" class="block w-full bg-teal-600 text-white px-4 py-2 rounded text-center hover:bg-teal-700 mt-3">
                Create Review Pack & Task
            </a>
        '''

        return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM - Client Profile</title>
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
            <h1 class="text-3xl font-bold">Client Profile: {{ client.display_name }}</h1>
            <p class="text-gray-600 mt-2">Extended client information and preferences</p>
            {% if request.args.get('msg') %}
            <div class="mt-4 p-4 bg-green-100 border border-green-300 text-green-800 rounded">
                {{ request.args.get('msg') }}
            </div>
            {% endif %}
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div class="bg-white rounded-lg shadow p-6">
                <h3 class="text-lg font-semibold mb-4">Basic Information</h3>
                <div class="space-y-3 text-sm">
                    <p><strong>Client ID:</strong> {{ client.client_id }}</p>
                    <p><strong>Name:</strong> {{ client.display_name }}</p>
                    <p><strong>Email:</strong> {{ client.email or 'N/A' }}</p>
                    <p><strong>Phone:</strong> {{ client.phone or 'N/A' }}</p>
                    <p><strong>Status:</strong> {{ client.status.title() }}</p>
                    <p><strong>Portfolio:</strong> £{{ "{:,.0f}".format(client.portfolio_value) }}</p>
                    <p><strong>Date Added:</strong> {{ client.date_added }}</p>
                </div>

                <div class="mt-6 space-y-2">
                    <a href="/clients/{{ client.client_id }}/communications" class="block w-full bg-blue-600 text-white px-4 py-2 rounded text-center hover:bg-blue-700">
                        Communications
                    </a>
                    <a href="/clients/{{ client.client_id }}/tasks" class="block w-full bg-green-600 text-white px-4 py-2 rounded text-center hover:bg-green-700">
                        Tasks & Reminders
                    </a>
                    <a href="/clients/{{ client.client_id }}/add_task" class="block w-full bg-indigo-600 text-white px-4 py-2 rounded text-center hover:bg-indigo-700">
                        Add New Task
                    </a>
                    ''' + review_button_html + '''
                </div>
            </div>

            <div class="lg:col-span-2">
                <div class="bg-white rounded-lg shadow p-6">
                    <form method="POST" class="space-y-6">
                        <h3 class="text-lg font-semibold mb-4">Address Information</h3>
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div class="md:col-span-2">
                                <label class="block text-sm font-medium text-gray-700 mb-1">Address Line 1</label>
                                <input type="text" name="address_line_1" value="{{ profile.address_line_1 if profile else '' }}" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                            </div>
                            <div class="md:col-span-2">
                                <label class="block text-sm font-medium text-gray-700 mb-1">Address Line 2</label>
                                <input type="text" name="address_line_2" value="{{ profile.address_line_2 if profile else '' }}" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">City</label>
                                <input type="text" name="city" value="{{ profile.city if profile else '' }}" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">County</label>
                                <input type="text" name="county" value="{{ profile.county if profile else '' }}" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">Postcode</label>
                                <input type="text" name="postcode" value="{{ profile.postcode if profile else '' }}" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">Country</label>
                                <input type="text" name="country" value="{{ profile.country if profile else 'UK' }}" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                            </div>
                        </div>

                        <h3 class="text-lg font-semibold mt-8 mb-4">Personal</h3>
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">Date of Birth</label>
                                <input type="date" name="date_of_birth" value="{{ profile.date_of_birth if profile else '' }}" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">Occupation</label>
                                <input type="text" name="occupation" value="{{ profile.occupation if profile else '' }}" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                            </div>
                            <div class="md:col-span-2">
                                <label class="block text-sm font-medium text-gray-700 mb-1">Employer</label>
                                <input type="text" name="employer" value="{{ profile.employer if profile else '' }}" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                            </div>
                        </div>

                        <h3 class="text-lg font-semibold mt-8 mb-4">Emergency Contact</h3>
                        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">Name</label>
                                <input type="text" name="emergency_contact_name" value="{{ profile.emergency_contact_name if profile else '' }}" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">Phone</label>
                                <input type="tel" name="emergency_contact_phone" value="{{ profile.emergency_contact_phone if profile else '' }}" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">Relationship</label>
                                <input type="text" name="emergency_contact_relationship" value="{{ profile.emergency_contact_relationship if profile else '' }}" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                            </div>
                        </div>

                        <h3 class="text-lg font-semibold mt-8 mb-4">Investment Preferences</h3>
                        <div class="space-y-4">
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">Investment Goals</label>
                                <textarea name="investment_goals" rows="3" class="w-full px-3 py-2 border border-gray-300 rounded-md">{{ profile.investment_goals if profile else '' }}</textarea>
                            </div>
                            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-1">Risk Profile</label>
                                    <select name="risk_profile" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                        <option value="">Select...</option>
                                        <option value="Conservative" {% if profile and profile.risk_profile == 'Conservative' %}selected{% endif %}>Conservative</option>
                                        <option value="Balanced" {% if profile and profile.risk_profile == 'Balanced' %}selected{% endif %}>Balanced</option>
                                        <option value="Growth" {% if profile and profile.risk_profile == 'Growth' %}selected{% endif %}>Growth</option>
                                        <option value="Aggressive" {% if profile and profile.risk_profile == 'Aggressive' %}selected{% endif %}>Aggressive</option>
                                    </select>
                                </div>
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-1">Preferred Contact</label>
                                    <select name="preferred_contact_method" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                        <option value="">Select...</option>
                                        <option value="Email" {% if profile and profile.preferred_contact_method == 'Email' %}selected{% endif %}>Email</option>
                                        <option value="Phone" {% if profile and profile.preferred_contact_method == 'Phone' %}selected{% endif %}>Phone</option>
                                        <option value="Post" {% if profile and profile.preferred_contact_method == 'Post' %}selected{% endif %}>Post</option>
                                        <option value="Meeting" {% if profile and profile.preferred_contact_method == 'Meeting' %}selected{% endif %}>Meeting</option>
                                    </select>
                                </div>
                                <div>
                                    <label class="block text sm font-medium text-gray-700 mb-1">Next Review Date</label>
                                    <input type="date" name="next_review_date" value="{{ profile.next_review_date if profile else '' }}" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                </div>
                            </div>
                        </div>

                        <div class="flex justify-between pt-6">
                            <a href="/clients" class="px-6 py-3 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">Back to Clients</a>
                            <button type="submit" class="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700">Save Profile</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </main>
</body>
</html>
        ''', client=client, profile=profile)

    except Exception as e:
        logger.error(f"Client profile error: {e}")
        return f"Error: {e}", 500

# ───────────────────────────────────────────
# NEW: Review button endpoint
# ───────────────────────────────────────────
@clients_bp.route('/clients/<client_id>/review')
def create_review(client_id):
    if 'credentials' not in session:
        return redirect(url_for('auth.authorize'))

    try:
        credentials = Credentials(**session['credentials'])
        drive = SimpleGoogleDrive(credentials)

        clients = drive.get_clients_enhanced()
        client = next((c for c in clients if c['client_id'] == client_id), None)
        if not client:
            return "Client not found", 404

        # Create Review {YEAR} structure + templates
        made = drive.create_review_pack_for_client(client)
        # Create Review Task (due in 14 days)
        task_ok = drive.create_review_task(client, due_in_days=14)

        msg = "Review pack created and task added." if (made and task_ok) \
            else "Review pack and/or task could not be created."
        # Redirect back to clients list with a message
        return redirect(url_for('clients.clients', msg=msg))

    except Exception as e:
        logger.error(f"Create review error: {e}")
        return f"Error: {e}", 500
