import stripe
import os
from dotenv import load_dotenv
import logging

load_dotenv() # Carga las variables de entorno desde .env

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configura tu clave secreta de Stripe.
# En producción, usa variables de entorno para mayor seguridad.
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

class PaymentError(Exception):
    """Excepción personalizada para errores de pago."""
    pass

async def process_payment(amount_cents: int, token: str, description: str, metadata: dict = None) -> str:
    """
    Procesa un pago usando Stripe.

    Args:
        amount_cents: Monto a cobrar en centavos (entero).
        token: El token de pago generado por Stripe.js en el frontend.
        description: Descripción del cargo.
        metadata: Un diccionario de datos para adjuntar al pago (ej. ID de usuario, tipo de servicio).

    Returns:
        El ID de la transacción de Stripe si el pago es exitoso.

    Raises:
        PaymentError: Si hay algún problema durante el proceso de pago.
    """
    if not stripe.api_key:
        logger.error("STRIPE_SECRET_KEY no está configurada. El pago no puede procesarse.")
        raise PaymentError("La clave secreta de Stripe no está configurada.")

    if amount_cents <= 0:
        raise PaymentError("El monto del pago debe ser positivo.")

    try:
        logger.info(f"Intentando procesar pago de {amount_cents / 100:.2f} USD con token {token}...")
        # Usamos PaymentIntent para mayor flexibilidad y manejo de SCA (Strong Customer Authentication)
        payment_intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency="usd",
            payment_method_data={"type": "card", "card": {"token": token}},
            confirm=True,
            description=description,
            metadata=metadata if metadata else {},
            # Agrega los detalles del cliente si están disponibles para mejorar la prevención de fraude
            # customer=customer_id,
            # receipt_email=customer_email,
            return_url="https://yourdomain.com/payment_success" # URL a la que Stripe redirigirá (puede no usarse si se confirma de inmediato)
        )

        if payment_intent.status == "succeeded":
            logger.info(f"Pago exitoso! PaymentIntent ID: {payment_intent.id}")
            return payment_intent.id
        else:
            logger.warning(f"El pago no se completó con éxito. Estado: {payment_intent.status}")
            raise PaymentError(f"El pago no pudo ser confirmado. Estado: {payment_intent.status}")

    except stripe.error.CardError as e:
        # Error específico de la tarjeta, ej. tarjeta rechazada
        body = e.json_body
        err = body.get('error', {})
        error_message = f"Error de tarjeta: {err.get('message', 'Desconocido')}"
        logger.error(error_message)
        raise PaymentError(error_message)
    except stripe.error.RateLimitError as e:
        # Demasiadas solicitudes a la API de Stripe en poco tiempo
        logger.error(f"Error de límite de tasa de Stripe: {e}")
        raise PaymentError("Demasiadas solicitudes, por favor inténtalo de nuevo más tarde.")
    except stripe.error.InvalidRequestError as e:
        # Parámetros inválidos
        logger.error(f"Error de solicitud inválida de Stripe: {e}")
        raise PaymentError("Solicitud de pago inválida.")
    except stripe.error.AuthenticationError as e:
        # Problemas de autenticación con la clave API de Stripe
        logger.error(f"Error de autenticación de Stripe: {e}")
        raise PaymentError("Error de autenticación con el servicio de pagos.")
    except stripe.error.APIConnectionError as e:
        # Problemas de conectividad de red
        logger.error(f"Error de conexión con la API de Stripe: {e}")
        raise PaymentError("Error de conexión con el servicio de pagos.")
    except stripe.error.StripeError as e:
        # Cualquier otro error de Stripe
        logger.error(f"Error general de Stripe: {e}")
        raise PaymentError("Ocurrió un error inesperado con el servicio de pagos.")
    except Exception as e:
        logger.error(f"Error inesperado al procesar el pago: {e}")
        raise PaymentError(f"Ocurrió un error inesperado: {e}")

# Ejemplo de uso (para pruebas locales)
async def main_test_payment():
    try:
        # Este token es solo un placeholder, en un sistema real,
        # se obtendría del frontend usando Stripe.js/Elements.
        # Usa un token de prueba válido (ej. de la documentación de Stripe para tarjetas de prueba).
        # Un token para tarjeta exitosa: 'tok_visa'
        # Un token para tarjeta rechazada: 'tok_chargeDeclined'
        test_token = "tok_visa"
        amount = 5000 # 50.00 USD en centavos (tarifa + envío + comisión)
        description = "Renovación de Matrícula FL - Placa ABC123"
        transaction_id = await process_payment(amount, test_token, description)
        print(f"Pago de prueba exitoso: {transaction_id}")
    except PaymentError as e:
        print(f"Error en el pago de prueba: {e}")
    except Exception as e:
        print(f"Error inesperado: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main_test_payment())
