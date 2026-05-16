"""Script temporal para listar modelos disponibles en WatsonX."""
import asyncio, httpx, os, json
from dotenv import load_dotenv

load_dotenv(".env")

API_KEY = os.getenv("IBM_BOB_API_KEY")
BASE_URL = os.getenv("IBM_BOB_BASE_URL", "https://us-south.ml.cloud.ibm.com/ml/v1")
PROJECT_ID = os.getenv("IBM_BOB_PROJECT_ID")
IAM_URL = "https://iam.cloud.ibm.com/identity/token"

async def main():
    # 1. Obtener IAM token
    async with httpx.AsyncClient() as c:
        r = await c.post(IAM_URL, headers={"Content-Type": "application/x-www-form-urlencoded"},
                         data={"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": API_KEY})
        r.raise_for_status()
        token = r.json()["access_token"]

    # 2. Consultar modelos
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    url = f"{BASE_URL}/foundation_model_specs?version=2023-05-29"
    async with httpx.AsyncClient() as c:
        r = await c.get(url, headers=headers)
        r.raise_for_status()
        models = r.json()

    # 3. Filtrar modelos granite
    granite_models = [m for m in models.get("resources", []) if "granite" in m.get("model_id", "").lower()]
    print(f"Total modelos disponibles: {len(models.get('resources', []))}")
    print(f"Modelos Granite encontrados: {len(granite_models)}")
    print()
    for m in granite_models:
        mid = m.get("model_id", "N/A")
        state = m.get("status", "N/A")
        print(f"  - {mid}  [{state}]")

    # 4. Mostrar también todos los modelos (sin tanto detalle)
    print(f"\n--- Todos los modelos ---")
    for m in models.get("resources", []):
        print(f"  {m.get('model_id', 'N/A')}")

if __name__ == "__main__":
    asyncio.run(main())
