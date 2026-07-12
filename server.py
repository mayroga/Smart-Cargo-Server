from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import uuid
import datetime
from functools import wraps
from werkzeug.utils import secure_filename # Importación corregida

app = Flask(__name__)
CORS(app)  # Habilitar CORS para permitir solicitudes desde el frontend

# --- Configuración ---
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload size
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}

# --- Datos en memoria (simulando una base de datos) ---
# Usuarios con roles (contraseña simplificada para demostración - ¡NO USAR EN PRODUCCIÓN!)
USERS = {
    'counter': {'password': 'password', 'role': 'counter', 'associated_shipper': None},
    'shipper1': {'password': 'password', 'role': 'shipper', 'associated_shipper': 'Acme Corp'}, # Asignar shipper al usuario
    'trucker1': {'password': 'password', 'role': 'trucker', 'associated_shipper': None},
    'weighbridge1': {'password': 'password', 'role': 'weighbridge', 'associated_shipper': None},
    'forwarder1': {'password': 'password', 'role': 'forwarder', 'associated_shipper': None}
}

# Envíos
SHIPMENTS = []
# Ejemplo inicial de envío
SHIPMENTS.append({
    'id': str(uuid.uuid4()),
    'hawb': 'HAWB12345',
    'mawb': 'MAWB67890',
    'origin': 'MIA',
    'destination': 'LAX',
    'shipper': 'Acme Corp', # Asegúrate de que este nombre coincida con 'associated_shipper' de shipper1
    'consignee': 'Global Logistics',
    'description': 'Electronic Components',
    'weight': 150.5,
    'dimensions': '100x80x50 cm',
    'status': 'Pending Confirmation',
    'documents': [],
    'notes': []
})

# --- Funciones Auxiliares ---
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def role_required(roles):
    """
    Decorador para restringir el acceso a ciertos roles.
    NOTA DE SEGURIDAD: En una aplicación real, esto se manejaría con tokens JWT
    o sesiones generadas por el servidor, no un encabezado fácilmente manipulable por el cliente.
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user_role = request.headers.get('X-User-Role')
            if not user_role or user_role not in roles:
                return jsonify({'message': 'Acceso no autorizado o rol insuficiente'}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator

# --- Rutas de la API ---

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    user_info = USERS.get(username)
    if user_info and user_info['password'] == password:
        return jsonify({'message': 'Login exitoso', 'role': user_info['role'], 'username': username}), 200
    return jsonify({'message': 'Credenciales inválidas'}), 401

@app.route('/api/shipments', methods=['GET'])
@role_required(['counter', 'shipper', 'trucker', 'weighbridge', 'forwarder'])
def get_shipments():
    user_role = request.headers.get('X-User-Role')
    username_requested = request.headers.get('X-Username') # Se necesita para filtrar por usuario
   
    # Simulación de filtrado por rol
    if user_role == 'shipper':
        # Un shipper solo ve sus propios envíos
        shipper_name = USERS.get(username_requested, {}).get('associated_shipper')
        if not shipper_name:
            return jsonify({'message': 'No se pudo determinar el nombre del shipper asociado.'}), 403
        return jsonify([s for s in SHIPMENTS if s['shipper'] == shipper_name]), 200
    elif user_role == 'trucker':
        # Un camionero solo ve envíos listos para recogida o en tránsito
        return jsonify([s for s in SHIPMENTS if s['status'] in ['Ready for Pickup', 'In Transit', 'Picked Up']]), 200 # Camionero también debería ver los que ya recogió
    elif user_role == 'weighbridge':
        # El de la báscula solo ve los que necesitan peso
        return jsonify([s for s in SHIPMENTS if s['status'] in ['Pending Weighing', 'Ready for Weighing']]), 200
    else: # counter, forwarder (o cualquier rol con acceso completo)
        return jsonify(SHIPMENTS), 200

@app.route('/api/shipments', methods=['POST'])
@role_required(['counter', 'forwarder'])
def add_shipment():
    data = request.json
    required_fields = ['hawb', 'mawb', 'origin', 'destination', 'shipper', 'consignee', 'description', 'weight', 'dimensions']
    if not all(k in data for k in required_fields):
        return jsonify({'message': f'Faltan campos obligatorios: {", ".join([k for k in required_fields if k not in data])}'}), 400

    try:
        weight = float(data['weight'])
    except ValueError:
        return jsonify({'message': 'El campo "weight" debe ser un número válido.'}), 400

    new_shipment = {
        'id': str(uuid.uuid4()),
        'hawb': data['hawb'],
        'mawb': data['mawb'],
        'origin': data['origin'],
        'destination': data['destination'],
        'shipper': data['shipper'],
        'consignee': data['consignee'],
        'description': data['description'],
        'weight': weight,
        'dimensions': data['dimensions'],
        'status': 'Pending Confirmation',
        'documents': [],
        'notes': [{'timestamp': str(datetime.datetime.now()), 'role': request.headers.get('X-User-Role'), 'note': 'Envío creado.'}]
    }
    SHIPMENTS.append(new_shipment)
    return jsonify(new_shipment), 201

@app.route('/api/shipments/<shipment_id>', methods=['PUT'])
@role_required(['counter', 'forwarder', 'weighbridge', 'trucker'])
def update_shipment(shipment_id):
    data = request.json
    user_role = request.headers.get('X-User-Role')
   
    shipment = next((s for s in SHIPMENTS if s['id'] == shipment_id), None)
    if not shipment:
        return jsonify({'message': 'Envío no encontrado'}), 404

    # Reglas de actualización por rol
    if user_role == 'weighbridge':
        if 'weight' in data:
            try:
                new_weight = float(data['weight'])
                shipment['weight'] = new_weight
                # Actualizar estado si el peso es el único campo relevante para el weighbridge
                if shipment['status'] == 'Pending Weighing':
                    shipment['status'] = 'Weighed'
                shipment['notes'].append({'timestamp': str(datetime.datetime.now()), 'role': user_role, 'note': f'Peso actualizado a {new_weight} kg.'})
                if 'note' in data and data['note'].strip(): # Añadir nota si existe
                    shipment['notes'].append({'timestamp': str(datetime.datetime.now()), 'role': user_role, 'note': data['note']})
                return jsonify(shipment), 200
            except ValueError:
                return jsonify({'message': 'El campo "weight" debe ser un número válido.'}), 400
        return jsonify({'message': 'El rol de báscula solo puede actualizar el peso.'}), 403
   
    elif user_role == 'trucker':
        if 'status' in data and data['status'] in ['Picked Up', 'Delivered']:
            if shipment['status'] in ['Ready for Pickup', 'In Transit', 'Picked Up']: # Permite Picked Up -> Delivered
                shipment['status'] = data['status']
                shipment['notes'].append({'timestamp': str(datetime.datetime.now()), 'role': user_role, 'note': f'Estado actualizado a {data["status"]}.'})
                if 'note' in data and data['note'].strip(): # Añadir nota si existe
                    shipment['notes'].append({'timestamp': str(datetime.datetime.now()), 'role': user_role, 'note': data['note']})
                return jsonify(shipment), 200
            else:
                return jsonify({'message': 'El estado no puede ser cambiado por un camionero en este momento.'}), 403
        return jsonify({'message': 'El rol de camionero solo puede actualizar el estado a "Picked Up" o "Delivered".'}), 403
   
    elif user_role in ['counter', 'forwarder']:
        # Los roles de counter/forwarder pueden actualizar cualquier campo (excepto ID, docs, notes directos)
        updated_fields = False
        for key, value in data.items():
            if key in shipment and key not in ['id', 'documents', 'notes']:
                if key == 'weight':
                    try:
                        shipment[key] = float(value)
                        updated_fields = True
                    except ValueError:
                        return jsonify({'message': 'El campo "weight" debe ser un número válido.'}), 400
                else:
                    shipment[key] = value
                    updated_fields = True
       
        # Si hay una nota, añadirla
        if 'note' in data and data['note'].strip():
            shipment['notes'].append({'timestamp': str(datetime.datetime.now()), 'role': user_role, 'note': data['note']})
            updated_fields = True

        if updated_fields:
            return jsonify(shipment), 200
        return jsonify({'message': 'No se proporcionaron campos válidos para actualizar.'}), 400
   
    return jsonify({'message': 'No tienes permisos para actualizar estos campos o el campo no es válido para tu rol.'}), 403

@app.route('/api/shipments/<shipment_id>/upload', methods=['POST'])
@role_required(['counter', 'shipper', 'forwarder']) # Trucker/Weighbridge pueden necesitar subir documentos en un futuro
def upload_document(shipment_id):
    user_role = request.headers.get('X-User-Role')
    shipment = next((s for s in SHIPMENTS if s['id'] == shipment_id), None)
    if not shipment:
        return jsonify({'message': 'Envío no encontrado'}), 404

    if 'file' not in request.files:
        return jsonify({'message': 'No se encontró el archivo en la solicitud'}), 400
   
    uploaded_files = request.files.getlist('file') # Permitir múltiples archivos
    if not uploaded_files or uploaded_files[0].filename == '':
        return jsonify({'message': 'No se seleccionó ningún archivo'}), 400

    uploaded_docs_info = []
    for file in uploaded_files:
        if file and allowed_file(file.filename):
            # Usar secure_filename importado de werkzeug.utils
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4()}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(filepath)
           
            document_info = {
                'filename': unique_filename,
                'original_name': filename,
                'uploaded_by': user_role,
                'timestamp': str(datetime.datetime.now()),
                'filepath': f"/uploads/{unique_filename}" # Ruta pública para acceder al archivo
            }
            shipment['documents'].append(document_info)
            shipment['notes'].append({'timestamp': str(datetime.datetime.now()), 'role': user_role, 'note': f'Documento "{filename}" subido.'})
            uploaded_docs_info.append(document_info)
        else:
            return jsonify({'message': f'Tipo de archivo no permitido para "{file.filename}"'}), 400

    return jsonify({'message': 'Archivo(s) subido(s) exitosamente', 'documents': uploaded_docs_info}), 200

# Ruta para servir los archivos subidos
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Ruta raíz para servir el frontend
@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
