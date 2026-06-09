import urllib.request, json

recetas = [
    {
        "nombre": "Hamburguesa Especial K-OS",
        "descripcion": "1. Sazona la carne con sal y pimienta.\n2. Forma una hamburguesa de 200g.\n3. Cocina en plancha 4 min por lado.\n4. Coloca en pan con tomate y cebolla.\n5. Sirve caliente.",
        "ingredientes_json": {"Carne": 0.2, "Tomate": 0.05, "Cebolla": 0.03}
    },
    {
        "nombre": "Tacos de Bistec K-OS",
        "descripcion": "1. Corta la carne en tiras finas.\n2. Sofrie con cebolla en aceite caliente.\n3. Agrega tomate picado y sazona.\n4. Calienta las tortillas.\n5. Sirve la carne sobre las tortillas.",
        "ingredientes_json": {"Carne": 0.15, "Cebolla": 0.05, "Tomate": 0.04, "Aceite": 0.02}
    },
    {
        "nombre": "Papas Fritas Giga",
        "descripcion": "1. Pela y corta las papas en bastones.\n2. Sumerge en agua fria 10 min.\n3. Seca bien con papel absorbente.\n4. Frie en aceite caliente 180C por 5 min.\n5. Escurre y sala al gusto.",
        "ingredientes_json": {"Papas": 0.35, "Aceite": 0.1}
    },
    {
        "nombre": "Pollo a la Plancha K-OS",
        "descripcion": "1. Marina el pollo con limon y ajo 15 min.\n2. Precalienta la plancha a fuego alto.\n3. Cocina 6 min por lado.\n4. Verifica que este bien cocido por dentro.\n5. Acompana con verduras al vapor.",
        "ingredientes_json": {"Pollo": 0.25, "Aceite": 0.01}
    }
]

for r in recetas:
    data = json.dumps(r).encode("utf-8")
    req = urllib.request.Request(
        "http://localhost:8000/api/recetas",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        resp = urllib.request.urlopen(req)
        nombre = r["nombre"]
        print(f"OK: {nombre}")
    except Exception as e:
        nombre = r["nombre"]
        print(f"Skip (ya existe): {nombre}")
