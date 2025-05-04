from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field # Importar Field
from typing import Optional # Importar Optional
from web3 import Web3
from eth_account import Account
from web3.exceptions import TransactionNotFound # Importar excepción específica

# RPC de Fuji Testnet
RPC_URL = "https://api.avax-test.network/ext/bc/C/rpc"
CHAIN_ID = 43113

# Conexión JJ
w3 = Web3(Web3.HTTPProvider(RPC_URL))
if not w3.is_connected():
    raise RuntimeError("No se pudo conectar a Fuji RPC")

app = FastAPI(title="Avalanche Loan Logging API", # Título actualizado
              description="API para registrar eventos de crédito en Fuji Testnet (Avalanche C-Chain)", # Descripción actualizada
              version="1.0.1") # Versión actualizada

class TxRequest(BaseModel):
    private_key: str
    to: str
    value_ether: float = Field(default=0.0) # Valor por defecto 0.0
    data: Optional[str] = None # Campo opcional para datos adicionales

@app.post("/log_event", summary="Registra un evento en la blockchain") # Endpoint renombrado y summary actualizado
def log_event_tx(req: TxRequest): # Función renombrada
    try:
        # Validar formato de la dirección de destino
        if not w3.is_address(req.to):
            raise HTTPException(status_code=400, detail="Dirección 'to' inválida")

        # Preparar cuenta
        try:
            acct = Account.from_key(req.private_key)
        except ValueError:
             raise HTTPException(status_code=400, detail="Clave privada inválida")

        nonce = w3.eth.get_transaction_count(acct.address)

        # Preparar transacción
        tx = {
            "from": acct.address, # Añadir 'from' es buena práctica aunque se infiere de la key
            "nonce": nonce,
            "to": req.to,
            "value": w3.to_wei(req.value_ether, "ether"), # Usará 0 si no se especifica
            "gasPrice": w3.eth.gas_price,
            "chainId": CHAIN_ID
        }

        # Añadir datos si se proporcionan
        if req.data:
            tx["data"] = req.data.encode('utf-8') # Codificar data como bytes UTF-8

        # Estimar gas (opcional pero recomendado si hay datos)
        try:
            estimated_gas = w3.eth.estimate_gas(tx)
            tx["gas"] = estimated_gas
        except Exception as estimate_error:
             # Si la estimación falla (ej. fondos insuficientes para gas), devolver error
             raise HTTPException(status_code=400, detail=f"Error estimando gas: {str(estimate_error)}")

        # Firmar la transacción
        try:
            signed_tx = acct.sign_transaction(tx)
        except Exception as sign_error:
             # Log detallado del error durante la firma
             print(f"Error during signing: {type(sign_error).__name__} - {sign_error}")
             raise HTTPException(status_code=500, detail=f"Error al firmar la transacción: {str(sign_error)}")

        # Verificar el objeto firmado antes de intentar acceder a raw_transaction (CORREGIDO)
        if not hasattr(signed_tx, 'raw_transaction'): # CORREGIDO a snake_case
            # Log para depuración si falta el atributo esperado
            print(f"DEBUG: Signed object type: {type(signed_tx)}")
            print(f"DEBUG: Signed object attributes: {dir(signed_tx)}")
            try:
                # Intentar imprimir el objeto si es posible
                print(f"DEBUG: Signed object value: {signed_tx}")
            except Exception:
                print("DEBUG: No se pudo imprimir el valor del objeto signed_tx.")
            # Lanzar un error claro indicando el problema
            raise HTTPException(status_code=500, detail="Error interno: El objeto firmado no tiene el atributo 'raw_transaction'. Revise los logs del servidor.") # Mensaje actualizado

        # Enviar la transacción firmada
        try:
            # CORREGIDO a snake_case
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        except Exception as send_error:
             # Log detallado del error durante el envío
             print(f"Error during sending: {type(send_error).__name__} - {send_error}")
             raise HTTPException(status_code=500, detail=f"Error al enviar la transacción: {str(send_error)}")

        # Esperar confirmación y obtener recibo
        try:
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        except Exception as receipt_error:
             # Log detallado del error esperando el recibo
             print(f"Error waiting for receipt: {type(receipt_error).__name__} - {receipt_error}")
             raise HTTPException(status_code=500, detail=f"Error esperando el recibo de la transacción: {str(receipt_error)}")

        return {
            "message": "Evento registrado exitosamente en blockchain.",
            "tx_hash": w3.to_hex(tx_hash),
            "status": receipt.status,
            "gas_used": receipt.gasUsed,
            "block_number": receipt.blockNumber,
            "logged_data": req.data # Devolver los datos enviados para confirmación
        }
    except ValueError as ve:
        # Captura errores como clave privada inválida o problemas de formato (aunque algunos ya se capturan antes)
        raise HTTPException(status_code=400, detail=f"Error de valor: {str(ve)}")
    except AttributeError as ae:
         # Capturar específicamente el AttributeError que vimos y loguearlo
         print(f"AttributeError capturado: {ae}")
         raise HTTPException(status_code=500, detail=f"Error interno del servidor (AttributeError): {str(ae)}")
    except Exception as e:
        # Captura otros errores generales (conexión, timeouts, fondos insuficientes no capturados antes, etc.)
        print(f"Error detallado: {type(e).__name__} - {e}") # Loguear error para depuración
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")

@app.get("/transaction_status/{tx_hash}", summary="Consulta el estado de una transacción por su hash")
def get_transaction_status(tx_hash: str):
    """
    Busca una transacción por su hash y devuelve su estado y detalles del recibo.
    """
    try:
        # Intenta obtener el recibo de la transacción
        receipt = w3.eth.get_transaction_receipt(tx_hash)

        # Si no se encuentra el recibo, la transacción no existe o no ha sido minada
        if receipt is None:
            raise HTTPException(status_code=404, detail="Transacción no encontrada o aún no minada.")

        # Devuelve los detalles relevantes del recibo
        return {
            "tx_hash": w3.to_hex(receipt.transactionHash), # Confirmar el hash consultado
            "status": receipt.status, # 1 para éxito, 0 para fallo
            "block_number": receipt.blockNumber,
            "block_hash": w3.to_hex(receipt.blockHash),
            "from": receipt.get('from'), # Usar .get() por si no está presente en algún nodo/receipt
            "to": receipt.get('to'),
            "gas_used": receipt.gasUsed,
            "cumulative_gas_used": receipt.cumulativeGasUsed,
            # Puedes añadir más campos del recibo si los necesitas
            # "logs": receipt.logs,
            # "contractAddress": receipt.contractAddress,
        }
    except TransactionNotFound:
        # Captura explícita si web3.py lanza esta excepción específica
         raise HTTPException(status_code=404, detail="Transacción no encontrada.")
    except ValueError as ve:
         # Captura errores como un formato de hash inválido
         raise HTTPException(status_code=400, detail=f"Hash de transacción inválido o error de formato: {str(ve)}")
    except Exception as e:
        # Captura otros errores generales (ej. problemas de conexión con el nodo RPC)
        print(f"Error consultando estado de tx {tx_hash}: {type(e).__name__} - {e}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor al consultar la transacción: {str(e)}")

@app.get("/health", summary="Chequea estado de conexión")
def health_check():
    return {"connected": w3.is_connected()}

# Para arrancar:
# uvicorn app:app --host 0.0.0.0 --port 8000

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
