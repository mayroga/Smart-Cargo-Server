from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional
import os
import logging
import asyncio # Necesario para tareas en segundo plano si se implementan
from datetime import datetime

# Importa los módulos del proyecto
from app.pagos import process_payment, PaymentError
from app.robot import run_dmv_automation, RobotAutomationError, CORPORATE_CARD_DETAILS
from app.database import create_db_and_tables, log_transaction

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Inicializa FastAPI
app = FastAPI(
    title="Mi App Trámites Automotrices",
    description="Aplicación para la renovación de matrículas vehiculares en USA con FastAPI y Playwright.",
    version="1.0.0"
)

# Configuración de CORS para permitir solicitudes desde el frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite todos los orígenes. En producción, especifica los dominios.
    allow_credentials=True,
    allow_methods=["*"],  # Permite todos los métodos (GET, POST, etc.)
    allow_headers=["*"],  # Permite todos los encabezados
)

# Monta el directorio estático para servir CSS, JS e imágenes
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Configura Jinja2 para servir plantillas HTML
templates = Jinja2Templates(directory="app/templates")

# Modelos Pydantic para validar los datos de entrada
class ClientData(BaseModel):
    nombre_completo: str
    direccion_envio: str
    telefono: str
    correo_electronico: EmailStr

class LicenseData(BaseModel):
    estado_emision_licencia: str
    numero_licencia: str
    fecha_expiracion_licencia: str

class VehicleData(BaseModel):
    numero_placa: str
    estado_vehiculo: str
    vin_ultimos_4: str

class RenewalRequest(BaseModel):
    client: ClientData
    license: LicenseData
    vehicle: VehicleData
    stripe_token: str # El token generado por Stripe.js en el frontend
    amount_total_cents: int # Monto total a cobrar en centavos

@app.on_event("startup")
async def startup_event():
    logger.info("La aplicación FastAPI está arrancando...")
    # Asegúrate de que el directorio 'data' exista para la DB
    os.makedirs("data", exist_ok=True)
    await create_db_and_tables()
    logger.info("Base de datos inicializada al arranque.")

@app.get("/", response_class=HTMLResponse, summary="Página de inicio del frontend")
async def read_root(request: Request):
    """
    Sirve la página HTML principal de la aplicación.
    """
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/v1/renovar", summary="Procesa la renovación de matrícula vehicular")
async def renovar_matricula(request_data: RenewalRequest):
    """
    Endpoint principal para iniciar el proceso de renovación de matrícula.
    1. Procesa el pago con Stripe.
    2. Si el pago es exitoso, ejecuta el robot de Playwright para automatizar el trámite en el DMV.
    3. Descarga el PDF del registro temporal y lo devuelve al cliente.
    """
    client_data = request_data.client
    license_data = request_data.license
    vehicle_data = request_data.vehicle
    stripe_token = request_data.stripe_token
    amount_total_cents = request_data.amount_total_cents

    transaction_id = "N/A"
    pdf_file_path = None
    transaction_status = "FALLO_PAGO"

    try:
        logger.info(f"Iniciando proceso de renovación para placa: {vehicle_data.numero_placa}, estado: {vehicle_data.estado_vehiculo}")

        # --- 1. Procesar el pago con Stripe ---
        payment_description = (
            f"Renovación Matrícula {vehicle_data.estado_vehiculo} - Placa: {vehicle_data.numero_placa} "
            f"({client_data.nombre_completo})"
        )
        payment_metadata = {
            "client_email": client_data.correo_electronico,
            "plate_number": vehicle_data.numero_placa,
            "vehicle_state": vehicle_data.estado_vehiculo
        }

        transaction_id = await process_payment(
            amount_total_cents,
            stripe_token,
            payment_description,
            payment_metadata
        )
        logger.info(f"Pago exitoso para la placa {vehicle_data.numero_placa}. ID de Transacción Stripe: {transaction_id}")
        transaction_status = "PAGO_EXITOSO"

        # --- 2. Ejecutar el robot de Playwright ---
        logger.info(f"Iniciando robot de automatización para {vehicle_data.estado_vehiculo}...")
        pdf_bytes = await run_dmv_automation(
            state=vehicle_data.estado_vehiculo,
            license_number=license_data.numero_licencia,
            license_exp=license_data.fecha_expiracion_licencia,
            plate_number=vehicle_data.numero_placa,
            vin_last_4=vehicle_data.vin_ultimos_4,
            corporate_card_details=CORPORATE_CARD_DETAILS # Asegúrate de que esto se carga de forma segura
        )
        logger.info(f"Robot completado. PDF generado para {vehicle_data.numero_placa}.")

        # --- Guardar el PDF temporalmente para el envío ---
        # En un sistema real, podrías querer almacenar esto en S3 o un blob storage
        # y guardar la URL. Para este ejemplo, lo guardamos localmente.
        pdf_filename = f"registro_temp_{vehicle_data.numero_placa}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        pdf_file_path = os.path.join("data", pdf_filename)
        with open(pdf_file_path, "wb") as f:
            f.write(pdf_bytes)
        logger.info(f"PDF guardado localmente en: {pdf_file_path}")
        transaction_status = "COMPLETADO_EXITOSO"

        # --- Registrar transacción final ---
        await log_transaction(
            client_name=client_data.nombre_completo,
            email=client_data.correo_electronico,
            plate_number=vehicle_data.numero_placa,
            vehicle_state=vehicle_data.estado_vehiculo,
            transaction_id=transaction_id,
            amount=amount_total_cents / 100,
            status=transaction_status,
            pdf_path=pdf_file_path
        )

        # --- 3. Devolver la respuesta al cliente ---
        return JSONResponse(status_code=200, content={
            "message": {
                "es": "¡Tu trámite ha sido procesado con éxito! Descarga tu comprobante temporal.",
                "en": "Your transaction has been processed successfully! Download your temporary proof."
            },
            "police_explanation": {
                "es": "¡Tu vehículo ya está legalmente renovado en el sistema del estado! Descarga este PDF en tu teléfono. Si un oficial de policía te detiene antes de recibir tu sticker físico, muéstrale este documento digital; es un comprobante legal 100% válido que demuestra que tu renovación está activa.",
                "en": "Your vehicle is now legally renewed in the state system! Download this PDF to your phone. If a police officer stops you before you receive your physical sticker, show them this digital document; it is a 100% valid legal proof that your renewal is active."
            },
            "shipping_explanation": {
                "es": "Tu sticker físico de la placa ha sido procesado exitosamente por el correo oficial. Te llegará a la dirección de envío que proporcionaste a través de correo postal regular (USPS) en los próximos días laborales.",
                "en": "Your physical license plate sticker has been successfully processed by official mail. It will arrive at the shipping address you provided via regular postal mail (USPS) in the next business days."
            },
            "pdf_url": f"/api/v1/download-pdf/{os.path.basename(pdf_file_path)}"
        })

    except PaymentError as e:
        logger.error(f"Error en el pago para {vehicle_data.numero_placa}: {e}")
        transaction_status = "FALLO_PAGO"
        await log_transaction(
            client_name=client_data.nombre_completo,
            email=client_data.correo_electronico,
            plate_number=vehicle_data.numero_placa,
            vehicle_state=vehicle_data.estado_vehiculo,
            transaction_id=transaction_id, # Será N/A o el ID parcial si falló antes de completar
            amount=amount_total_cents / 100,
            status=transaction_status
        )
        raise HTTPException(status_code=400, detail={"es": str(e), "en": str(e)}) # Devolver mensaje traducido sería mejor

    except RobotAutomationError as e:
        logger.error(f"Error en la automatización del robot para {vehicle_data.numero_placa}: {e}")
        transaction_status = "FALLO_ROBOT"
        await log_transaction(
            client_name=client_data.nombre_completo,
            email=client_data.correo_electronico,
            plate_number=vehicle_data.numero_placa,
            vehicle_state=vehicle_data.estado_vehiculo,
            transaction_id=transaction_id,
            amount=amount_total_cents / 100,
            status=transaction_status
        )
        raise HTTPException(status_code=500, detail={"es": str(e), "en": str(e)})

    except Exception as e:
        logger.error(f"Error inesperado en el endpoint /api/v1/renovar para {vehicle_data.numero_placa}: {e}", exc_info=True)
        transaction_status = "FALLO_INESPERADO"
        await log_transaction(
            client_name=client_data.nombre_completo,
            email=client_data.correo_electronico,
            plate_number=vehicle_data.numero_placa,
            vehicle_state=vehicle_data.estado_vehiculo,
            transaction_id=transaction_id,
            amount=amount_total_cents / 100,
            status=transaction_status
        )
        raise HTTPException(status_code=500, detail={
            "es": "Ocurrió un error inesperado al procesar tu solicitud. Por favor, inténtalo de nuevo más tarde.",
            "en": "An unexpected error occurred while processing your request. Please try again later."
        })

@app.get("/api/v1/download-pdf/{filename}", summary="Descarga el PDF de registro temporal")
async def download_pdf(filename: str):
    """
    Permite al cliente descargar el PDF de registro temporal.
    """
    file_path = os.path.join("data", filename)
    if not os.path.exists(file_path):
        logger.warning(f"Intento de descarga de PDF no existente: {filename}")
        raise HTTPException(status_code=404, detail={"es": "Archivo no encontrado.", "en": "File not found."})
    
    return FileResponse(path=file_path, filename=filename, media_type="application/pdf")

# Opcional: Ruta para verificar la salud del servicio
@app.get("/health", summary="Verificación de salud del servicio")
async def health_check():
    return {"status": "ok"}

# Uvicorn entry point
if __name__ == "__main__":
    import uvicorn
    # Para desarrollo local, asegúrate de tener el archivo .env configurado
    # con STRIPE_SECRET_KEY.
    uvicorn.run(app, host="0.0.0.0", port=8000)
