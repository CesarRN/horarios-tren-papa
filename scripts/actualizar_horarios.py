#!/usr/bin/env python3
"""
Descarga el dataset oficial GTFS de Renfe (Alta Velocidad / Larga Distancia /
Media Distancia) y genera un data/horarios.json con los trenes entre las
estaciones de Madrid y "El Herradón - La Cañada", para los próximos N días.

Fuente oficial: https://data.renfe.com/es/dataset/horarios-de-alta-velocidad-larga-distancia-y-media-distancia
Licencia: Creative Commons Attribution 4.0

Este script está pensado para ejecutarse cada noche desde un GitHub Action
(ver .github/workflows/actualizar_horarios.yml), pero también se puede
ejecutar a mano:

    python3 scripts/actualizar_horarios.py

No necesita librerías externas: solo la biblioteca estándar de Python.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import sys
import urllib.request
import zipfile
from collections import defaultdict

GTFS_URL = "https://ssl.renfe.com/gtransit/Fichero_AV_LD/google_transit.zip"
DIAS_A_GENERAR = 14  # cuántos días hacia adelante incluir en el JSON
SALIDA_JSON = "data/horarios.json"

# Nombres (o fragmentos) de estación a buscar dentro de stops.txt.
# Se busca por coincidencia parcial, sin tener en cuenta mayúsculas/acentos,
# así que no hace falta que sea exacto. Si Renfe cambia el nombre exacto de
# una estación, basta con ajustar estas listas.
DESTINO_FRAGMENTOS = ["herradon", "canada"]  # El Herradón - La Cañada
MADRID_FRAGMENTOS = {
    "Madrid-Chamartín": ["chamartin"],
    "Madrid-Atocha": ["atocha"],
    "Madrid-Príncipe Pío": ["principe pio"],
}

# Cómo dividir el día en "mañana" y "tarde". Formato HH:MM. Un tren con hora
# de salida ANTES de este límite se considera de mañana; igual o después, de
# tarde.
LIMITE_TARDE = "14:00"


def normaliza(texto: str) -> str:
    """minúsculas y sin acentos, para comparar nombres de estación."""
    equivalencias = str.maketrans("áéíóúÁÉÍÓÚñÑ", "aeiouAEIOUnN")
    return texto.translate(equivalencias).lower()


def descargar_gtfs(url: str) -> zipfile.ZipFile:
    print(f"Descargando {url} ...")
    with urllib.request.urlopen(url, timeout=120) as resp:
        datos = resp.read()
    print(f"Descargado ({len(datos) / 1_000_000:.1f} MB)")
    return zipfile.ZipFile(io.BytesIO(datos))


def lee_csv(zf: zipfile.ZipFile, nombre: str) -> list[dict]:
    with zf.open(nombre) as f:
        texto = io.TextIOWrapper(f, encoding="utf-8-sig")
        return list(csv.DictReader(texto))


def encuentra_stop_ids(stops: list[dict], fragmentos: list[str]) -> set[str]:
    encontrados = set()
    for s in stops:
        nombre_norm = normaliza(s["stop_name"])
        if any(frag in nombre_norm for frag in fragmentos):
            encontrados.add(s["stop_id"])
    return encontrados


def construye_calendario(calendar: list[dict], calendar_dates: list[dict],
                          dias: list[dt.date]) -> dict[str, set[dt.date]]:
    """Para cada service_id, el conjunto de fechas (dentro de `dias`) en que circula."""
    activos: dict[str, set[dt.date]] = defaultdict(set)
    dias_semana = ["monday", "tuesday", "wednesday", "thursday", "friday",
                    "saturday", "sunday"]

    if calendar:
        columnas = set(calendar[0].keys())
        print(f"Columnas de calendar.txt: {sorted(columnas)}")
    if calendar_dates:
        print(f"Columnas de calendar_dates.txt: {sorted(calendar_dates[0].keys())}")

    minimo, maximo = min(dias), max(dias)

    for row in calendar:
        sid = row.get("service_id")
        if not sid:
            continue
        ini_str, fin_str = row.get("start_date"), row.get("end_date")
        # Si el feed no trae rango de fechas, asumimos que aplica a todo el
        # periodo consultado y dejamos que calendar_dates.txt afine el resto.
        ini = dt.datetime.strptime(ini_str, "%Y%m%d").date() if ini_str else minimo
        fin = dt.datetime.strptime(fin_str, "%Y%m%d").date() if fin_str else maximo
        for d in dias:
            if ini <= d <= fin and row.get(dias_semana[d.weekday()]) == "1":
                activos[sid].add(d)

    for row in calendar_dates:
        sid = row.get("service_id")
        fecha_str = row.get("date")
        tipo = row.get("exception_type")
        if not sid or not fecha_str:
            continue
        fecha = dt.datetime.strptime(fecha_str, "%Y%m%d").date()
        if fecha in dias:
            if tipo == "1":
                activos[sid].add(fecha)
            elif tipo == "2":
                activos[sid].discard(fecha)

    return activos


def hhmm(gtfs_time: str) -> str:
    """GTFS permite horas >=24:00 (viajes que cruzan medianoche). Las normaliza a HH:MM."""
    h, m, _s = gtfs_time.split(":")
    h = int(h) % 24
    return f"{h:02d}:{m}"


def es_de_tarde(hora: str) -> bool:
    return hora >= LIMITE_TARDE


def main() -> None:
    hoy = dt.date.today()
    dias = [hoy + dt.timedelta(days=i) for i in range(DIAS_A_GENERAR)]

    zf = descargar_gtfs(GTFS_URL)

    print("Leyendo stops.txt ...")
    stops = lee_csv(zf, "stops.txt")
    nombre_por_id = {s["stop_id"]: s["stop_name"] for s in stops}

    destino_ids = encuentra_stop_ids(stops, DESTINO_FRAGMENTOS)
    if not destino_ids:
        print("ERROR: no se ha encontrado ninguna parada que coincida con "
              f"{DESTINO_FRAGMENTOS}. Revisa stops.txt del GTFS.", file=sys.stderr)
        sys.exit(1)
    print(f"Estación destino encontrada: "
          f"{[nombre_por_id[i] for i in destino_ids]}")

    madrid_ids = {}
    for etiqueta, frags in MADRID_FRAGMENTOS.items():
        ids = encuentra_stop_ids(stops, frags)
        if ids:
            madrid_ids[etiqueta] = ids
            print(f"  {etiqueta}: {[nombre_por_id[i] for i in ids]}")
    todas_madrid_ids = set().union(*madrid_ids.values()) if madrid_ids else set()
    if not todas_madrid_ids:
        print("ERROR: no se ha encontrado ninguna estación de Madrid. "
              "Revisa MADRID_FRAGMENTOS.", file=sys.stderr)
        sys.exit(1)

    def etiqueta_madrid(stop_id: str) -> str:
        for etiqueta, ids in madrid_ids.items():
            if stop_id in ids:
                return etiqueta
        return nombre_por_id.get(stop_id, stop_id)

    print("Leyendo calendar.txt / calendar_dates.txt ...")
    calendar = lee_csv(zf, "calendar.txt") if "calendar.txt" in zf.namelist() else []
    calendar_dates = lee_csv(zf, "calendar_dates.txt") if "calendar_dates.txt" in zf.namelist() else []
    activos = construye_calendario(calendar, calendar_dates, dias)

    print("Leyendo trips.txt ...")
    trips = lee_csv(zf, "trips.txt")
    service_por_trip = {t["trip_id"]: t["service_id"] for t in trips}

    print("Leyendo stop_times.txt (puede tardar un poco) ...")
    stop_times = lee_csv(zf, "stop_times.txt")

    paradas_por_trip: dict[str, list[dict]] = defaultdict(list)
    for st in stop_times:
        if st["stop_id"] in todas_madrid_ids or st["stop_id"] in destino_ids:
            paradas_por_trip[st["trip_id"]].append(st)

    ida = defaultdict(list)    # Madrid -> Cañada, por fecha ISO
    vuelta = defaultdict(list)  # Cañada -> Madrid, por fecha ISO

    for trip_id, paradas in paradas_por_trip.items():
        madrid_parada = next((p for p in paradas if p["stop_id"] in todas_madrid_ids), None)
        destino_parada = next((p for p in paradas if p["stop_id"] in destino_ids), None)
        if not madrid_parada or not destino_parada:
            continue  # el trip pasa por una de las dos pero no por ambas

        service_id = service_por_trip.get(trip_id)
        fechas = activos.get(service_id, set())
        if not fechas:
            continue

        seq_madrid = int(madrid_parada["stop_sequence"])
        seq_destino = int(destino_parada["stop_sequence"])

        if seq_madrid < seq_destino:
            # Va de Madrid hacia La Cañada
            salida = hhmm(madrid_parada["departure_time"])
            llegada = hhmm(destino_parada["arrival_time"])
            registro = {
                "salida": salida,
                "estacion_origen": etiqueta_madrid(madrid_parada["stop_id"]),
                "llegada": llegada,
                "estacion_destino": "El Herradón - La Cañada",
                "franja": "tarde" if es_de_tarde(salida) else "mañana",
            }
            for f in fechas:
                ida[f.isoformat()].append(registro)
        else:
            # Va de La Cañada hacia Madrid
            salida = hhmm(destino_parada["departure_time"])
            llegada = hhmm(madrid_parada["arrival_time"])
            registro = {
                "salida": salida,
                "estacion_origen": "El Herradón - La Cañada",
                "llegada": llegada,
                "estacion_destino": etiqueta_madrid(madrid_parada["stop_id"]),
                "franja": "tarde" if es_de_tarde(salida) else "mañana",
            }
            for f in fechas:
                vuelta[f.isoformat()].append(registro)

    for coleccion in (ida, vuelta):
        for f in coleccion:
            vistos = set()
            unicos = []
            for r in coleccion[f]:
                clave = (r["salida"], r["estacion_origen"], r["llegada"], r["estacion_destino"])
                if clave not in vistos:
                    vistos.add(clave)
                    unicos.append(r)
            unicos.sort(key=lambda r: r["salida"])
            coleccion[f] = unicos

    resultado = {
        "generado": dt.datetime.now().isoformat(timespec="seconds"),
        "fuente": GTFS_URL,
        "limite_tarde": LIMITE_TARDE,
        "ida": ida,
        "vuelta": vuelta,
    }

    with open(SALIDA_JSON, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2, sort_keys=True)

    total_ida = sum(len(v) for v in ida.values())
    total_vuelta = sum(len(v) for v in vuelta.values())
    print(f"Escrito {SALIDA_JSON}: {total_ida} trenes de ida, "
          f"{total_vuelta} trenes de vuelta, en {len(dias)} días.")


if __name__ == "__main__":
    main()
