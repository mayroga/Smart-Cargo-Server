document.addEventListener('DOMContentLoaded', () => {
    const SERVER_URL = 'http://127.0.0.1:5000'; // Asegúrate de que coincida con la URL de tu backend Flask

    // --- Referencias a elementos del DOM ---
    const loginContainer = document.getElementById('login-container');
    const loginForm = document.getElementById('login-form');
    const loginErrorMessage = document.getElementById('login-error-message');
    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');

    const dashboardContainer = document.getElementById('dashboard-container');
    const userDisplay = document.getElementById('user-display');
    const roleDisplay = document.getElementById('role-display');
    const logoutBtn = document.getElementById('logout-btn');
    const addShipmentBtn = document.getElementById('add-shipment-btn');
    const shipmentTableBody = document.getElementById('shipment-table-body');
    const noShipmentsMessage = document.getElementById('no-shipments-message');

    const addEditShipmentModal = document.getElementById('add-edit-shipment-modal');
    const modalTitle = document.getElementById('modal-title');
    const shipmentForm = document.getElementById('shipment-form');
    const shipmentIdInput = document.getElementById('shipment-id');
    const formHawb = document.getElementById('form-hawb');
    const formMawb = document.getElementById('form-mawb');
    const formOrigin = document.getElementById('form-origin');
    const formDestination = document.getElementById('form-destination');
    const formShipper = document.getElementById('form-shipper');
    const formConsignee = document.getElementById('form-consignee');
    const formDescription = document.getElementById('form-description');
    const formWeight = document.getElementById('form-weight');
    const formDimensions = document.getElementById('form-dimensions');
    const formStatus = document.getElementById('form-status');
    const formNote = document.getElementById('form-note');
    const cancelAddEditBtn = document.getElementById('cancel-add-edit-btn');

    const documentUploadSection = document.getElementById('document-upload-section');
    const documentUploadForm = document.getElementById('document-upload-form');
    const documentFileInput = document.getElementById('document-file-input');
    const documentUploadMessage = document.getElementById('document-upload-message');
    const shipmentNotesList = document.getElementById('shipment-notes-list');

    const documentViewerModal = document.getElementById('document-viewer-modal');
    const docViewerHawb = document.getElementById('doc-viewer-hawb');
    const documentsList = document.getElementById('documents-list');
    const closeDocViewerBtn = document.getElementById('close-doc-viewer-btn');

    // --- Variables de estado ---
    let currentUserRole = localStorage.getItem('userRole');
    let currentUsername = localStorage.getItem('username'); // Para filtrado de usuario específico
    let editingShipmentId = null;

    // --- Funciones Auxiliares ---
    const showElement = (element) => element.classList.remove('hidden');
    const hideElement = (element) => element.classList.add('hidden');
    const clearForm = (form) => form.reset();

    const displayMessage = (element, message, isError = false) => {
        element.textContent = message;
        element.className = isError ? 'error-message' : 'message';
        showElement(element);
        setTimeout(() => hideElement(element), 5000); // Ocultar después de 5 segundos
    };

    const getAuthHeaders = () => ({
        'X-User-Role': currentUserRole,
        'X-Username': currentUsername,
        'Content-Type': 'application/json'
    });

    // --- Lógica de Autenticación ---
    const handleLogin = async (event) => {
        event.preventDefault();
        const username = usernameInput.value;
        const password = passwordInput.value;

        try {
            const response = await fetch(`${SERVER_URL}/api/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });
            const data = await response.json();

            if (response.ok) {
                localStorage.setItem('userRole', data.role);
                localStorage.setItem('username', username);
                currentUserRole = data.role;
                currentUsername = username;
                renderUIByRole();
                hideElement(loginContainer);
                showElement(dashboardContainer);
            } else {
                displayMessage(loginErrorMessage, data.message, true);
            }
        } catch (error) {
            console.error('Error durante el login:', error);
            displayMessage(loginErrorMessage, 'Error de conexión con el servidor.', true);
        }
    };

    const logout = () => {
        localStorage.removeItem('userRole');
        localStorage.removeItem('username');
        currentUserRole = null;
        currentUsername = null;
        window.location.reload(); // Recargar la página para volver a la pantalla de login
    };

    // --- Lógica de Renderizado de UI por Rol ---
    const renderUIByRole = () => {
        userDisplay.textContent = currentUsername;
        roleDisplay.textContent = currentUserRole.toUpperCase();

        const addEditElements = document.querySelectorAll('.add-edit-visibility');
        const statusInput = document.querySelector('.status-input-visibility');
        const noteInput = document.querySelector('.note-input-visibility');
        const documentUploadVisibility = document.querySelectorAll('.document-upload-visibility');

        // Resetear visibilidad por defecto antes de aplicar por rol
        addEditElements.forEach(el => hideElement(el));
        hideElement(statusInput);
        hideElement(noteInput);
        documentUploadVisibility.forEach(el => hideElement(el));

        if (currentUserRole === 'counter' || currentUserRole === 'forwarder') {
            addEditElements.forEach(el => showElement(el));
            showElement(statusInput);
            showElement(noteInput);
            documentUploadVisibility.forEach(el => showElement(el));
        } else if (currentUserRole === 'shipper') {
            documentUploadVisibility.forEach(el => showElement(el)); // Shipper puede subir docs
            // Otros elementos add/edit permanecen ocultos para shipper
        }
        // Los roles 'trucker' y 'weighbridge' no tienen acceso a añadir/editar directamente ni a la subida de docs general.
       
        fetchAndDisplayShipments();
    };

    // --- Lógica de Gestión de Envíos ---
    const fetchAndDisplayShipments = async () => {
        shipmentTableBody.innerHTML = '<tr><td colspan="10" class="text-center">Cargando envíos...</td></tr>';
        hideElement(noShipmentsMessage);

        try {
            const response = await fetch(`${SERVER_URL}/api/shipments`, {
                method: 'GET',
                headers: getAuthHeaders()
            });
            const shipments = await response.json();

            if (!response.ok) {
                shipmentTableBody.innerHTML = `<tr><td colspan="10" class="text-center error-message">${shipments.message || 'Error al cargar envíos.'}</td></tr>`;
                return;
            }

            shipmentTableBody.innerHTML = ''; // Limpiar la tabla
            if (shipments.length === 0) {
                showElement(noShipmentsMessage);
                return;
            }

            shipments.forEach(shipment => {
                const row = shipmentTableBody.insertRow();
                row.innerHTML = `
                    <td data-label="HAWB">${shipment.hawb}</td>
                    <td data-label="MAWB">${shipment.mawb}</td>
                    <td data-label="Origen">${shipment.origin}</td>
                    <td data-label="Destino">${shipment.destination}</td>
                    <td data-label="Shipper">${shipment.shipper}</td>
                    <td data-label="Consignee">${shipment.consignee}</td>
                    <td data-label="Estado">${shipment.status}</td>
                    <td data-label="Peso (kg)">${shipment.weight}</td>
                    <td data-label="Dimensiones">${shipment.dimensions}</td>
                    <td data-label="Acciones" class="action-buttons">
                        <button class="btn secondary-btn small-btn view-docs-btn" data-id="${shipment.id}">Ver Docs</button>
                        ${(currentUserRole === 'counter' || currentUserRole === 'forwarder') ?
                            `<button class="btn primary-btn small-btn edit-shipment-btn" data-id="${shipment.id}">Editar</button>` : ''}
                        ${currentUserRole === 'weighbridge' && (shipment.status === 'Pending Weighing' || shipment.status === 'Ready for Weighing') ?
                            `<button class="btn info-btn small-btn update-weight-btn" data-id="${shipment.id}">Actualizar Peso</button>` : ''}
                        ${currentUserRole === 'trucker' && shipment.status === 'Ready for Pickup' ?
                            `<button class="btn success-btn small-btn update-status-btn" data-id="${shipment.id}" data-status="Picked Up">Recogido</button>` : ''}
                        ${currentUserRole === 'trucker' && shipment.status === 'Picked Up' ?
                            `<button class="btn success-btn small-btn update-status-btn" data-id="${shipment.id}" data-status="Delivered">Entregado</button>` : ''}
                    </td>
                `;
            });
        } catch (error) {
            console.error('Error al cargar los envíos:', error);
            shipmentTableBody.innerHTML = '<tr><td colspan="10" class="text-center error-message">No se pudieron cargar los envíos.</td></tr>';
        }
    };

    const openAddEditModal = async (shipment = null) => {
        clearForm(shipmentForm);
        hideElement(documentUploadSection);
        shipmentNotesList.innerHTML = '';
        documentUploadMessage.textContent = '';
        documentFileInput.value = '';

        if (shipment) {
            editingShipmentId = shipment.id;
            modalTitle.textContent = 'Editar Envío';
            shipmentIdInput.value = shipment.id;
            formHawb.value = shipment.hawb;
            formMawb.value = shipment.mawb;
            formOrigin.value = shipment.origin;
            formDestination.value = shipment.destination;
            formShipper.value = shipment.shipper;
            formConsignee.value = shipment.consignee;
            formDescription.value = shipment.description;
            formWeight.value = shipment.weight;
            formDimensions.value = shipment.dimensions;
            formStatus.value = shipment.status;

            // Mostrar sección de documentos y notas si es una edición y el rol lo permite
            if (['counter', 'forwarder', 'shipper'].includes(currentUserRole)) {
                showElement(documentUploadSection);
            }

            // Mostrar notas
            if (shipment.notes && shipment.notes.length > 0) {
                shipmentNotesList.innerHTML = ''; // Limpiar cualquier mensaje predeterminado
                shipment.notes.forEach(note => {
                    const li = document.createElement('li');
                    li.textContent = `[${new Date(note.timestamp).toLocaleString()}] (${note.role}): ${note.note}`;
                    shipmentNotesList.appendChild(li);
                });
            } else {
                shipmentNotesList.innerHTML = '<li>No hay notas para este envío.</li>';
            }

            // Deshabilitar campos según el rol
            const isFullAdmin = (currentUserRole === 'counter' || currentUserRole === 'forwarder');
            formHawb.disabled = !isFullAdmin;
            formMawb.disabled = !isFullAdmin;
            formOrigin.disabled = !isFullAdmin;
            formDestination.disabled = !isFullAdmin;
            formShipper.disabled = !isFullAdmin;
            formConsignee.disabled = !isFullAdmin;
            formDescription.disabled = !isFullAdmin;
            formDimensions.disabled = !isFullAdmin;

            formWeight.disabled = !(isFullAdmin || currentUserRole === 'weighbridge');
            formStatus.disabled = !(isFullAdmin || currentUserRole === 'trucker'); // Trucker puede cambiar a Picked Up/Delivered
           
            // Asegurarse de que el input de nota se muestre/oculte correctamente
            const noteInputContainer = formNote.closest('.form-group.note-input-visibility');
            if (isFullAdmin || currentUserRole === 'weighbridge' || currentUserRole === 'trucker') {
                showElement(noteInputContainer);
            } else {
                hideElement(noteInputContainer);
            }

        } else { // Añadir nuevo envío
            editingShipmentId = null;
            modalTitle.textContent = 'Añadir Nuevo Envío';
            formStatus.value = 'Pending Confirmation'; // Estado inicial
            // Habilitar todos los campos para añadir si el rol lo permite
            if (currentUserRole === 'counter' || currentUserRole === 'forwarder') {
                formHawb.disabled = false;
                formMawb.disabled = false;
                formOrigin.disabled = false;
                formDestination.disabled = false;
                formShipper.disabled = false;
                formConsignee.disabled = false;
                formDescription.disabled = false;
                formDimensions.disabled = false;
                formWeight.disabled = false;
                formStatus.disabled = false;
                showElement(formNote.closest('.form-group.note-input-visibility'));
            } else {
                // Si se abrió el modal por error para un rol no permitido, deshabilitar todo
                formHawb.disabled = true;
                formMawb.disabled = true;
                formOrigin.disabled = true;
                formDestination.disabled = true;
                formShipper.disabled = true;
                formConsignee.disabled = true;
                formDescription.disabled = true;
                formDimensions.disabled = true;
                formWeight.disabled = true;
                formStatus.disabled = true;
                hideElement(formNote.closest('.form-group.note-input-visibility'));
            }
        }
        showElement(addEditShipmentModal);
    };

    const handleSaveShipment = async (event) => {
        event.preventDefault();
        const shipmentData = {
            hawb: formHawb.value,
            mawb: formMawb.value,
            origin: formOrigin.value,
            destination: formDestination.value,
            shipper: formShipper.value,
            consignee: formConsignee.value,
            description: formDescription.value,
            weight: parseFloat(formWeight.value),
            dimensions: formDimensions.value,
            status: formStatus.value,
            note: formNote.value.trim()
        };

        const method = editingShipmentId ? 'PUT' : 'POST';
        const url = editingShipmentId ? `${SERVER_URL}/api/shipments/${editingShipmentId}` : `${SERVER_URL}/api/shipments`;

        try {
            const response = await fetch(url, {
                method: method,
                headers: getAuthHeaders(),
                body: JSON.stringify(shipmentData)
            });
            const data = await response.json();

            if (response.ok) {
                hideElement(addEditShipmentModal);
                displayMessage(document.querySelector('.app-container'), `Envío ${editingShipmentId ? 'actualizado' : 'añadido'} exitosamente.`); // Mensaje general
                fetchAndDisplayShipments(); // Refrescar la tabla
            } else {
                displayMessage(documentUploadMessage, data.message || 'Error al guardar el envío.', true);
            }
        } catch (error) {
            console.error('Error al guardar el envío:', error);
            displayMessage(documentUploadMessage, 'Error de conexión al guardar el envío.', true);
        }
    };

    const handleUploadDocument = async (event) => {
        event.preventDefault();
        if (!editingShipmentId) {
            displayMessage(documentUploadMessage, 'Primero selecciona un envío para subir documentos.', true);
            return;
        }

        const files = documentFileInput.files;
        if (files.length === 0) {
            displayMessage(documentUploadMessage, 'Por favor, selecciona al menos un archivo.', true);
            return;
        }

        const formData = new FormData();
        for (let i = 0; i < files.length; i++) {
            formData.append('file', files[i]);
        }

        try {
            const response = await fetch(`${SERVER_URL}/api/shipments/${editingShipmentId}/upload`, {
                method: 'POST',
                headers: {
                    'X-User-Role': currentUserRole, // No Content-Type aquí para FormData
                    'X-Username': currentUsername
                },
                body: formData
            });
            const data = await response.json();

            if (response.ok) {
                displayMessage(documentUploadMessage, data.message || 'Documento(s) subido(s) exitosamente.');
                // Recargar los envíos para actualizar las notas y documentos si el modal estuviera abierto
                const currentShipment = await fetch(`${SERVER_URL}/api/shipments`, { headers: getAuthHeaders() }).then(res => res.json()).then(shipments => shipments.find(s => s.id === editingShipmentId));
                if (currentShipment) {
                    openAddEditModal(currentShipment); // Reabrir el modal con los datos actualizados
                }
            } else {
                displayMessage(documentUploadMessage, data.message || 'Error al subir el documento.', true);
            }
        } catch (error) {
            console.error('Error al subir el documento:', error);
            displayMessage(documentUploadMessage, 'Error de conexión al subir el documento.', true);
        } finally {
            documentFileInput.value = ''; // Limpiar el input de archivo
        }
    };

    const viewDocuments = async (shipmentId) => {
        try {
            const response = await fetch(`${SERVER_URL}/api/shipments`, { headers: getAuthHeaders() });
            const shipments = await response.json();
            const shipment = shipments.find(s => s.id === shipmentId);

            if (!shipment) {
                alert('Envío no encontrado para ver documentos.');
                return;
            }

            docViewerHawb.textContent = shipment.hawb;
            documentsList.innerHTML = ''; // Limpiar lista anterior

            if (shipment.documents && shipment.documents.length > 0) {
                shipment.documents.forEach(doc => {
                    const docItem = document.createElement('div');
                    docItem.className = 'document-item';
                    docItem.innerHTML = `
                        <a href="${SERVER_URL}${doc.filepath}" target="_blank">${doc.original_name}</a>
                        <span>Subido por: ${doc.uploaded_by} el ${new Date(doc.timestamp).toLocaleString()}</span>
                    `;
                    documentsList.appendChild(docItem);
                });
            } else {
                documentsList.innerHTML = '<p class="text-center">No hay documentos para este envío.</p>';
            }
            showElement(documentViewerModal);
        } catch (error) {
            console.error('Error al obtener documentos:', error);
            alert('Error al cargar los documentos.');
        }
    };

    const updateShipmentField = async (shipmentId, field, value, note = '') => {
        const payload = { [field]: value };
        if (note) payload.note = note;

        try {
            const response = await fetch(`${SERVER_URL}/api/shipments/${shipmentId}`, {
                method: 'PUT',
                headers: getAuthHeaders(),
                body: JSON.stringify(payload)
            });
            const data = await response.json();

            if (response.ok) {
                alert(`Envío ${field === 'weight' ? 'pesado' : 'actualizado'} exitosamente.`);
                fetchAndDisplayShipments();
            } else {
                alert(data.message || `Error al actualizar el ${field}.`);
            }
        } catch (error) {
            console.error(`Error al actualizar el ${field}:`, error);
            alert('Error de conexión al actualizar el envío.');
        }
    };

    // --- Event Listeners ---
    loginForm.addEventListener('submit', handleLogin);
    logoutBtn.addEventListener('click', logout);
    addShipmentBtn.addEventListener('click', () => {
        if (currentUserRole === 'counter' || currentUserRole === 'forwarder') {
            openAddEditModal();
        } else {
            alert('No tienes permisos para añadir nuevos envíos.');
        }
    });
    cancelAddEditBtn.addEventListener('click', () => hideElement(addEditShipmentModal));
    closeDocViewerBtn.addEventListener('click', () => hideElement(documentViewerModal));
    shipmentForm.addEventListener('submit', handleSaveShipment);
    documentUploadForm.addEventListener('submit', handleUploadDocument);

    // Delegación de eventos para botones de la tabla de envíos
    shipmentTableBody.addEventListener('click', async (event) => {
        const target = event.target;
        const shipmentId = target.dataset.id;

        if (target.classList.contains('edit-shipment-btn')) {
            // Obtener el envío específico para edición
            try {
                const response = await fetch(`${SERVER_URL}/api/shipments`, { headers: getAuthHeaders() });
                if (!response.ok) throw new Error(response.statusText);
                const shipments = await response.json();
                const shipmentToEdit = shipments.find(s => s.id === shipmentId);
                if (shipmentToEdit) {
                    openAddEditModal(shipmentToEdit);
                } else {
                    alert('Envío no encontrado para editar.');
                }
            } catch (error) {
                console.error('Error al obtener envío para editar:', error);
                alert('Error al cargar la información del envío.');
            }
        } else if (target.classList.contains('view-docs-btn')) {
            viewDocuments(shipmentId);
        } else if (target.classList.contains('update-weight-btn')) {
            const newWeight = prompt('Introduce el nuevo peso (kg):');
            if (newWeight !== null && !isNaN(newWeight) && newWeight.trim() !== '') {
                updateShipmentField(shipmentId, 'weight', newWeight, `Peso actualizado a ${newWeight} kg.`);
            } else if (newWeight !== null) {
                alert('Peso inválido. Por favor, introduce un número.');
            }
        } else if (target.classList.contains('update-status-btn')) {
            const newStatus = target.dataset.status;
            const confirmUpdate = confirm(`¿Estás seguro de que quieres cambiar el estado a "${newStatus}"?`);
            if (confirmUpdate) {
                updateShipmentField(shipmentId, 'status', newStatus, `Estado cambiado a ${newStatus}.`);
            }
        }
    });

    // --- Inicialización ---
    if (currentUserRole && currentUsername) {
        hideElement(loginContainer);
        showElement(dashboardContainer);
        renderUIByRole();
    } else {
        showElement(loginContainer);
        hideElement(dashboardContainer);
    }
});
