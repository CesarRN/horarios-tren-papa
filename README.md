# Horarios de tren — Madrid ↔ El Herradón-La Cañada

Web muy sencilla y accesible con los horarios de tren entre Madrid y
El Herradón-La Cañada, pensada para instalarse como una app en el
iPhone (sin App Store, sin coste).

Los horarios se generan cada noche automáticamente a partir del
[dataset oficial y abierto de Renfe](https://data.renfe.com/es/dataset/horarios-de-alta-velocidad-larga-distancia-y-media-distancia)
(Alta Velocidad / Larga Distancia / Media Distancia). No hace falta
tocar nada a mano.

## Desplegarla (una sola vez, ~10 minutos)

1. **Crea un repositorio nuevo en GitHub** (público o privado, da igual),
   por ejemplo `horarios-tren-papa`.
2. **Sube estos archivos** a ese repositorio. Desde la carpeta de este
   proyecto:
   ```bash
   git remote add origin https://github.com/TU_USUARIO/horarios-tren-papa.git
   git add -A
   git commit -m "Primera versión"
   git branch -M main
   git push -u origin main
   ```
3. **Activa GitHub Pages**: en el repositorio, ve a
   `Settings → Pages`, y en "Build and deployment" elige
   `Deploy from a branch`, rama `main`, carpeta `/ (root)`. Guarda.
   En un par de minutos tu web estará en
   `https://TU_USUARIO.github.io/horarios-tren-papa/`.
4. **Comprueba que la actualización automática funciona**: en la
   pestaña `Actions` del repositorio, entra en el workflow
   "Actualizar horarios de tren" y pulsa "Run workflow" para
   lanzarlo una vez a mano. Si todo va bien, verás un commit nuevo
   con `data/horarios.json` actualizado. A partir de ahí se ejecutará
   solo, cada noche.

## Enviársela a tu padre

Abre `https://TU_USUARIO.github.io/horarios-tren-papa/` en tu propio
iPhone, envíasela por WhatsApp a tu padre. Él, al abrir el enlace:

1. Toca el botón "Compartir" (el cuadrado con la flecha) en Safari.
2. Elige "Añadir a pantalla de inicio".

Le quedará un icono como el de cualquier app, a pantalla completa,
sin barras de Safari.

## Si algún día deja de funcionar

Lo más probable es que Renfe haya cambiado el nombre exacto de alguna
estación en su archivo de datos. En la pestaña `Actions` del
repositorio verás el log de la última ejecución: si falla, imprime
qué estaciones ha encontrado y con qué nombres, lo que ayuda a saber
qué ajustar en `scripts/actualizar_horarios.py` (las listas
`DESTINO_FRAGMENTOS` y `MADRID_FRAGMENTOS`, al principio del archivo).
Dímelo y te ayudo a arreglarlo.

## Estructura del proyecto

```
index.html                          la web (una sola página)
manifest.json, sw.js, icon-*.png    lo necesario para instalarla como app
data/horarios.json                  horarios ya calculados (se regenera solo)
scripts/actualizar_horarios.py      script que descarga y filtra el GTFS de Renfe
.github/workflows/...yml            la tarea programada que lo ejecuta cada noche
```
