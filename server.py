```python
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

    ```

    ---

**[index.html]**
```html
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>MIA Counter Agent App</title>
        <link rel="stylesheet" href="style.css"> <!-- Referencia a style.css -->
        <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='currentColor' d='M11 19c0 .5-.5 1-1 1s-1-.5-1-1v-2h2v2zm0-4c0 .5-.5 1-1 1s-1-.5-1-1v-2h2v2zm0-4c0 .5-.5 1-1 1s-1-.5-1-1V9h2v2zm0-4c0 .5-.5 1-1 1s-1-.5-1-1V5h2v2zm7-2v2h-2V5h2zM5 5h2v2H5V5zm10 0v2h-2V5h2zm-5 4V7H8V5H6v4h4zm-4 0h2v2H6V9zm0 4h2v2H6v-2zm0 4h2v2H6v-2zm12-4h-2v2h2v-2zm0 4h-2v2h2v-2zm0-8h-2V7h2v2zm-4 12V5h-2v16h2zM4 3h16c1.1 0 2 .9 2 2v14c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V5c0-1.1.9-2 2-2z'%3E%3C/path%3E%3C/svg%3E" type="image/svg+xml">
    </head>
    <body>
        <div class="app-container">
            <!-- Sección de Login -->
            <div id="login-container" class="card login-card">
                <h2>Bienvenido a MIA Cargo</h2>
                <form id="login-form" class="form-grid">
                    <div class="form-group">
                        <label for="username">Usuario:</label>
                        <input type="text" id="username" class="input-field" required>
                    </div>
                    <div class="form-group">
                        <label for="password">Contraseña:</label>
                        <input type="password" id="password" class="input-field" required>
                    </div>
                    <button type="submit" class="btn primary-btn full-width">Iniciar Sesión</button>
                </form>
                <p id="login-error-message" class="error-message"></p>
            </div>

            <!-- Sección del Dashboard Principal (oculta hasta el login) -->
            <div id="dashboard-container" class="hidden">
                <header class="dashboard-header">
                    <h1>Panel de Control de Envíos</h1>
                    <div class="user-info">
                        Bienvenido, <span id="user-display"></span> (<span id="role-display"></span>)
                        <button id="logout-btn" class="btn secondary-btn small-btn">Cerrar Sesión</button>
                    </div>
                </header>

                <div class="toolbar">
                    <button id="add-shipment-btn" class="btn primary-btn add-edit-visibility">Añadir Envío</button>
                </div>

                <div class="shipment-list-container card">
                    <h2>Lista de Envíos</h2>
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>HAWB</th>
                                <th>MAWB</th>
                                <th>Origen</th>
                                <th>Destino</th>
                                <th>Shipper</th>
                                <th>Consignee</th>
                                <th>Estado</th>
                                <th>Peso (kg)</th>
                                <th>Dimensiones</th>
                                <th>Acciones</th>
                            </tr>
                        </thead>
                        <tbody id="shipment-table-body">
                            <!-- Los envíos se cargarán aquí dinámicamente -->
                            <tr><td colspan="10" class="text-center">Cargando envíos...</td></tr>
                        </tbody>
                    </table>
                    <p id="no-shipments-message" class="text-center hidden">No hay envíos disponibles.</p>
                </div>
            </div>

            <!-- Modal para Añadir/Editar Envío -->
            <div id="add-edit-shipment-modal" class="modal-overlay hidden">
                <div class="modal-content">
                    <h3 id="modal-title">Añadir Nuevo Envío</h3>
                    <form id="shipment-form" class="form-grid">
                        <input type="hidden" id="shipment-id">
                        <div class="form-group">
                            <label for="form-hawb">HAWB:</label>
                            <input type="text" id="form-hawb" class="input-field" required>
                        </div>
                        <div class="form-group">
                            <label for="form-mawb">MAWB:</label>
                            <input type="text" id="form-mawb" class="input-field" required>
                        </div>
                        <div class="form-group">
                            <label for="form-origin">Origen:</label>
                            <input type="text" id="form-origin" class="input-field" required>
                        </div>
                        <div class="form-group">
                            <label for="form-destination">Destino:</label>
                            <input type="text" id="form-destination" class="input-field" required>
                        </div>
                        <div class="form-group">
                            <label for="form-shipper">Shipper:</label>
                            <input type="text" id="form-shipper" class="input-field" required>
                        </div>
                        <div class="form-group">
                            <label for="form-consignee">Consignee:</label>
                            <input type="text" id="form-consignee" class="input-field" required>
                        </div>
                        <div class="form-group">
                            <label for="form-description">Descripción:</label>
                            <input type="text" id="form-description" class="input-field" required>
                        </div>
                        <div class="form-group">
                            <label for="form-weight">Peso (kg):</label>
                            <input type="number" step="0.1" id="form-weight" class="input-field" required>
                        </div>
                        <div class="form-group">
                            <label for="form-dimensions">Dimensiones:</label>
                            <input type="text" id="form-dimensions" class="input-field" required>
                        </div>
                        <div class="form-group status-input-visibility">
                            <label for="form-status">Estado:</label>
                            <select id="form-status" class="input-field">
                                <option value="Pending Confirmation">Pendiente Confirmación</option>
                                <option value="Ready for Pickup">Listo para Recogida</option>
                                <option value="Picked Up">Recogido</option>
                                <option value="In Transit">En Tránsito</option>
                                <option value="Customs Check">Revisión Aduanera</option>
                                <option value="Pending Weighing">Pendiente Pesaje</option>
                                <option value="Weighed">Pesado</option>
                                <option value="Ready for Delivery">Listo para Entrega</option>
                                <option value="Delivered">Entregado</option>
                                <option value="Cancelled">Cancelado</option>
                            </select>
                        </div>
                        <div class="form-group note-input-visibility">
                            <label for="form-note">Nota (opcional):</label>
                            <textarea id="form-note" class="input-field"></textarea>
                        </div>
                        <div class="modal-actions full-width">
                            <button type="submit" class="btn primary-btn">Guardar Envío</button>
                            <button type="button" id="cancel-add-edit-btn" class="btn secondary-btn">Cancelar</button>
                        </div>
                    </form>

                    <!-- Sección de Subida de Documentos dentro del modal -->
                    <div id="document-upload-section" class="document-upload-visibility hidden">
                        <h4>Subir Documentos</h4>
                        <form id="document-upload-form">
                            <input type="file" id="document-file-input" class="input-field" multiple>
                            <button type="submit" class="btn primary-btn small-btn">Subir</button>
                        </form>
                        <div id="document-upload-message" class="message"></div>
                    </div>

                    <!-- Sección de notas del envío -->
                    <div class="shipment-notes-section">
                        <h4>Historial de Notas</h4>
                        <ul id="shipment-notes-list">
                            <!-- Las notas se cargarán aquí -->
                        </ul>
                    </div>
                </div>
            </div>

            <!-- Modal para Ver Documentos -->
            <div id="document-viewer-modal" class="modal-overlay hidden">
                <div class="modal-content">
                    <h3>Documentos del Envío <span id="doc-viewer-hawb"></span></h3>
                    <div id="documents-list">
                        <!-- Los documentos se cargarán aquí dinámicamente -->
                    </div>
                    <div class="modal-actions">
                        <button type="button" id="close-doc-viewer-btn" class="btn secondary-btn">Cerrar</button>
                    </div>
                </div>
            </div>
        </div>

        <script src="script.js"></script> <!-- Referencia al script JavaScript -->
    </body>
    </html>
    ```

    ---

**[style.css]**
 ```css
    /* --- Base Styles & Reset --- */
    :root {
        --primary-color: #007bff;
        --secondary-color: #6c757d;
        --success-color: #28a745;
        --danger-color: #dc3545;
        --warning-color: #ffc107;
        --info-color: #17a2b8;
        --light-color: #f8f9fa;
        --dark-color: #343a40;
        --white-color: #ffffff;
        --gray-100: #f8f9fa;
        --gray-200: #e9ecef;
        --gray-300: #dee2e6;
        --gray-400: #ced4da;
        --gray-500: #adb5bd;
        --gray-600: #6c757d;
        --gray-700: #495057;
        --gray-800: #343a40;
        --gray-900: #212529;

        --border-radius: 0.375rem;
        --spacing-xs: 0.25rem;
        --spacing-sm: 0.5rem;
        --spacing-md: 1rem;
        --spacing-lg: 1.5rem;
        --spacing-xl: 2rem;

        --font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        --font-size-base: 1rem;
        --line-height-base: 1.5;
    }

    *, *::before, *::after {
        box-sizing: border-box;
        margin: 0;
        padding: 0;
    }

    body {
        font-family: var(--font-family);
        font-size: var(--font-size-base);
        line-height: var(--line-height-base);
        color: var(--dark-color);
        background-color: var(--gray-100);
        margin: 0;
        padding: 0;
        display: flex;
        justify-content: center;
        align-items: flex-start; /* Alineación arriba para no centrar el body verticalmente */
        min-height: 100vh;
    }

    /* --- Utility Classes --- */
    .hidden {
        display: none !important;
    }

    .full-width {
        grid-column: 1 / -1; /* Ocupa todo el ancho en un grid */
        width: 100%; /* Asegura que ocupe el 100% de su contenedor */
    }

    .text-center {
        text-align: center;
    }

    .text-right {
        text-align: right;
    }

    .error-message {
        color: var(--danger-color);
        margin-top: var(--spacing-sm);
        text-align: center;
    }

    .message {
        margin-top: var(--spacing-md);
        padding: var(--spacing-sm);
        border-radius: var(--border-radius);
        background-color: var(--info-color);
        color: var(--white-color);
        font-size: 0.9em;
    }

    /* --- Container & Layout --- */
    .app-container {
        width: 100%;
        max-width: 1200px; /* Ancho máximo para el contenido principal */
        margin: var(--spacing-xl) auto; /* Margen superior e inferior para separación */
        padding: 0 var(--spacing-md);
    }

    .flex-row {
        display: flex;
        flex-direction: row;
        gap: var(--spacing-md);
    }

    .flex-col {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-md);
    }

    /* --- Card Component --- */
    .card {
        background-color: var(--white-color);
        border-radius: var(--border-radius);
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.05);
        padding: var(--spacing-lg);
        margin-bottom: var(--spacing-lg); /* Espacio entre tarjetas */
    }

    /* --- Login Specific Styles --- */
    .login-card {
        max-width: 400px;
        margin: var(--spacing-xl) auto; /* Centrar verticalmente en la vista si es lo único */
        padding: var(--spacing-xl);
        text-align: center;
    }

    .login-card h2 {
        color: var(--primary-color);
        margin-bottom: var(--spacing-lg);
        font-size: 1.8rem;
    }

    /* --- Dashboard Header --- */
    .dashboard-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background-color: var(--dark-color);
        color: var(--white-color);
        padding: var(--spacing-md) var(--spacing-lg);
        border-radius: var(--border-radius);
        margin-bottom: var(--spacing-lg);
    }

    .dashboard-header h1 {
        font-size: 1.5rem;
        margin: 0;
    }

    .user-info {
        font-size: 0.9rem;
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
    }

    .user-info span {
        font-weight: bold;
    }

    /* --- Toolbar (Buttons above tables) --- */
    .toolbar {
        margin-bottom: var(--spacing-lg);
        display: flex;
        gap: var(--spacing-md);
    }

    /* --- Forms & Input Fields --- */
    .form-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); /* Columnas responsivas */
        gap: var(--spacing-md);
    }

    .form-group {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-xs);
    }

    .form-group label {
        font-weight: 600;
        color: var(--gray-700);
        font-size: 0.9em;
    }

    .input-field,
    select.input-field,
    textarea.input-field {
        padding: var(--spacing-sm) var(--spacing-md);
        border: 1px solid var(--gray-400);
        border-radius: var(--border-radius);
        font-size: var(--font-size-base);
        color: var(--gray-900);
        background-color: var(--white-color);
        transition: border-color 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
        width: 100%; /* Asegura que el input ocupe todo el ancho disponible */
    }

    .input-field:focus,
    select.input-field:focus,
    textarea.input-field:focus {
        outline: none;
        border-color: var(--primary-color);
        box-shadow: 0 0 0 0.2rem rgba(0, 123, 255, 0.25);
    }

    textarea.input-field {
        min-height: 80px;
        resize: vertical;
    }

    /* --- Buttons --- */
    .btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: var(--spacing-sm) var(--spacing-lg);
        font-size: var(--font-size-base);
        font-weight: 600;
        text-align: center;
        text-decoration: none;
        white-space: nowrap;
        border: 1px solid transparent;
        border-radius: var(--border-radius);
        cursor: pointer;
        transition: all 0.2s ease-in-out;
    }

    .btn:hover {
        opacity: 0.9;
        transform: translateY(-1px);
    }

    .btn:active {
        transform: translateY(0);
    }

    .primary-btn {
        background-color: var(--primary-color);
        color: var(--white-color);
        border-color: var(--primary-color);
    }

    .primary-btn:hover {
        background-color: #0069d9;
        border-color: #0062cc;
    }

    .secondary-btn {
        background-color: var(--secondary-color);
        color: var(--white-color);
        border-color: var(--secondary-color);
    }

    .secondary-btn:hover {
        background-color: #545b62;
        border-color: #4e555b;
    }

    .danger-btn {
        background-color: var(--danger-color);
        color: var(--white-color);
        border-color: var(--danger-color);
    }

    .small-btn {
        padding: var(--spacing-xs) var(--spacing-md);
        font-size: 0.8em;
    }

    /* --- Table Styles --- */
    .data-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: var(--spacing-md);
        font-size: 0.9rem;
    }

    .data-table th,
    .data-table td {
        padding: var(--spacing-sm) var(--spacing-md);
        border: 1px solid var(--gray-300);
        text-align: left;
    }

    .data-table th {
        background-color: var(--gray-200);
        font-weight: 700;
        color: var(--gray-700);
        white-space: nowrap; /* Evita que los encabezados se envuelvan */
    }

    .data-table tbody tr:nth-child(even) {
        background-color: var(--gray-100);
    }

    .data-table tbody tr:hover {
        background-color: var(--gray-200);
    }

    .data-table .action-buttons {
        display: flex;
        gap: var(--spacing-xs);
        flex-wrap: wrap;
        justify-content: center;
    }

    .data-table .action-buttons .btn {
        padding: var(--spacing-xs) var(--spacing-sm);
        font-size: 0.75em;
    }

    /* --- Modals --- */
    .modal-overlay {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-color: rgba(0, 0, 0, 0.6);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 1000;
    }

    .modal-content {
        background-color: var(--white-color);
        border-radius: var(--border-radius);
        box-shadow: 0 8px 16px rgba(0, 0, 0, 0.2);
        padding: var(--spacing-xl);
        max-width: 900px;
        width: 90%;
        max-height: 90vh; /* Altura máxima para permitir scroll */
        overflow-y: auto; /* Scroll si el contenido es demasiado largo */
        position: relative;
        animation: fadeInScale 0.3s ease-out forwards;
    }

    @keyframes fadeInScale {
        from {
            opacity: 0;
            transform: scale(0.9);
        }
        to {
            opacity: 1;
            transform: scale(1);
        }
    }


    .modal-content h3 {
        margin-top: 0;
        margin-bottom: var(--spacing-lg);
        color: var(--primary-color);
        text-align: center;
    }

    .modal-actions {
        display: flex;
        justify-content: flex-end;
        gap: var(--spacing-md);
        margin-top: var(--spacing-xl);
    }

    .modal-content h4 {
        margin-top: var(--spacing-lg);
        margin-bottom: var(--spacing-sm);
        color: var(--gray-800);
        border-bottom: 1px solid var(--gray-300);
        padding-bottom: var(--spacing-xs);
    }

    /* Document Upload Section */
    #document-upload-section {
        margin-top: var(--spacing-xl);
        padding-top: var(--spacing-md);
        border-top: 1px solid var(--gray-300);
    }

    #document-upload-form {
        display: flex;
        gap: var(--spacing-md);
        align-items: center;
        margin-bottom: var(--spacing-md);
    }

    #document-file-input {
        flex-grow: 1;
    }

    /* Document Viewer */
    #documents-list {
        margin-top: var(--spacing-md);
        display: flex;
        flex-wrap: wrap;
        gap: var(--spacing-md);
    }

    #documents-list .document-item {
        background-color: var(--gray-100);
        border: 1px solid var(--gray-300);
        border-radius: var(--border-radius);
        padding: var(--spacing-sm);
        font-size: 0.9em;
        display: flex;
        flex-direction: column;
        gap: var(--spacing-xs);
        flex: 1 1 auto; /* Permite que los elementos se ajusten */
        min-width: 200px; /* Ancho mínimo para cada documento */
    }

    #documents-list .document-item a {
        color: var(--primary-color);
        text-decoration: none;
        font-weight: 500;
    }

    #documents-list .document-item a:hover {
        text-decoration: underline;
    }

    #documents-list .document-item span {
        color: var(--gray-600);
        font-size: 0.8em;
    }

    /* Shipment Notes Section */
    .shipment-notes-section {
        margin-top: var(--spacing-lg);
        padding-top: var(--spacing-md);
        border-top: 1px solid var(--gray-300);
    }

    #shipment-notes-list {
        list-style: none;
        padding: 0;
        margin-top: var(--spacing-sm);
    }

    #shipment-notes-list li {
        background-color: var(--gray-50);
        border-bottom: 1px solid var(--gray-200);
        padding: var(--spacing-xs) var(--spacing-sm);
        font-size: 0.85em;
        color: var(--gray-700);
    }

    #shipment-notes-list li:last-child {
        border-bottom: none;
    }

    /* Responsive adjustments */
    @media (max-width: 768px) {
        .dashboard-header {
            flex-direction: column;
            align-items: flex-start;
            gap: var(--spacing-sm);
        }
        .data-table thead {
            display: none; /* Oculta la cabecera en pantallas pequeñas */
        }
        .data-table, .data-table tbody, .data-table tr, .data-table td {
            display: block;
            width: 100%;
        }
        .data-table tr {
            margin-bottom: var(--spacing-md);
            border: 1px solid var(--gray-300);
            border-radius: var(--border-radius);
            background-color: var(--white-color);
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.03);
        }
        .data-table td {
            text-align: right;
            padding-left: 50%; /* Espacio para la etiqueta virtual */
            position: relative;
            border: none;
            border-bottom: 1px dashed var(--gray-200);
        }
        .data-table td:before {
            content: attr(data-label); /* Usa el atributo data-label */
            position: absolute;
            left: var(--spacing-md);
            width: calc(50% - var(--spacing-lg));
            padding-right: var(--spacing-md);
            white-space: nowrap;
            text-align: left;
            font-weight: 600;
            color: var(--gray-700);
        }
        .data-table td:last-child {
            border-bottom: none;
        }
        .form-grid {
            grid-template-columns: 1fr; /* Una columna en móviles */
        }
        .modal-actions {
            flex-direction: column;
        }
        .modal-actions .btn {
            width: 100%;
        }
        #document-upload-form {
            flex-direction: column;
            align-items: stretch;
        }
    }
    ```

    ---
