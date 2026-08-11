import aiosqlite
import logging

# Configuración de logging para visibilidad
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DATABASE_URL = "data/transactions.db" # Usaremos SQLite para este ejemplo

async def create_db_and_tables():
    """Crea la base de datos y la tabla de transacciones si no existen."""
    try:
        async with aiosqlite.connect(DATABASE_URL) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    plate_number TEXT NOT NULL,
                    vehicle_state TEXT NOT NULL,
                    transaction_id TEXT NOT NULL,
                    amount REAL NOT NULL,
                    status TEXT NOT NULL,
                    pdf_path TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()
            logger.info("Base de datos y tabla 'transactions' creadas o ya existentes.")
    except Exception as e:
        logger.error(f"Error al inicializar la base de datos: {e}")

async def log_transaction(
    client_name: str,
    email: str,
    plate_number: str,
    vehicle_state: str,
    transaction_id: str,
    amount: float,
    status: str,
    pdf_path: str = None
):
    """Registra una transacción en la base de datos."""
    try:
        async with aiosqlite.connect(DATABASE_URL) as db:
            await db.execute("""
                INSERT INTO transactions (client_name, email, plate_number, vehicle_state, transaction_id, amount, status, pdf_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (client_name, email, plate_number, vehicle_state, transaction_id, amount, status, pdf_path))
            await db.commit()
            logger.info(f"Transacción {transaction_id} registrada con estado: {status}")
    except Exception as e:
        logger.error(f"Error al registrar la transacción {transaction_id}: {e}")

# Asegúrate de que el directorio 'data' exista
import os
os.makedirs("data", exist_ok=True)
