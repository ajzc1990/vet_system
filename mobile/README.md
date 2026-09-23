# VeterSystem móvil

App para el veterinario y el personal de la clínica (React Native + Expo SDK 57).
Usa la API REST de Django en `apps/api/` con login por token.

## Qué hace

- **Agenda:** turnos del día con navegación entre días. Nuevo turno (botón flotante), editar, confirmar, cancelar
  y "Atender", que abre la consulta vinculada al turno.
- **Pacientes:** búsqueda por mascota, tutor o DNI, y alta de cliente con su primera mascota.
- **Ficha del paciente:**
  - datos del paciente y del tutor (llamar, WhatsApp, agendar turno, cargar otra mascota), con edición;
  - internación activa y resumen con IA (se puede generar si la IA está habilitada);
  - vacunas (el carnet en PDF se comparte), consultas, recetas (en PDF, para compartir), estudios y fotos,
    y desparasitaciones.
- **Acciones médicas:** consulta, vacuna, receta, estudio con la cámara, desparasitación e internación.
  Solo las ven los roles VET y ADMIN, igual que en la web.
- **Internados:** sala de internación, controles (evoluciones con signos vitales), alta o cierre, e informe en PDF.

## Correr en desarrollo

1. Levantar Django escuchando en la red local (no solo en localhost):

   ```powershell
   # PowerShell, desde la raíz del proyecto, con la base SQLite local
   $env:USE_POSTGRES='False'; $env:DEBUG='True'
   .\venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000
   ```

   Agregar la IP de la PC a `ALLOWED_HOSTS` en el `.env` (por ejemplo `ALLOWED_HOSTS=127.0.0.1,localhost,192.168.0.10`).

2. Configurar la app:

   ```powershell
   cd mobile
   Copy-Item .env.example .env.local   # y poner la IP de tu PC
   npm install
   npx expo start
   ```

3. Instalar **Expo Go** en el celular, conectado al mismo wifi que la PC, y escanear el QR.
   Usuario de prueba: `demo_vet` / `Demo2026!` (cargarlo con `python manage.py seed_demo`).

## Chequeos

```bash
npx tsc --noEmit
npx expo lint
```

## Estructura

```
src/
  app/                      rutas (Expo Router)
    _layout.tsx             sesión + guardas de login
    login.tsx
    (app)/(tabs)/           Agenda, Pacientes, Mi cuenta
    (app)/mascota/[id]/     ficha + formularios de consulta, vacuna y receta
  components/               UI compartida y helpers de formularios
  lib/                      cliente de API, sesión (token en SecureStore), tipos, fechas
```

## Generar la app instalable (EAS)

Las builds instaladas apuntan siempre a `https://vetersystem.com` ([src/lib/api.ts](src/lib/api.ts)).
`EXPO_PUBLIC_API_URL` solo se usa en desarrollo con Expo Go.

```bash
npx eas-cli@latest build --profile preview --platform android      # APK para repartir con un link
npx eas-cli@latest build --profile production --platform android   # .aab para Google Play
```

## Actualizaciones sin reinstalar (EAS Update)

Los cambios que son solo de pantallas o lógica (archivos de `src/`) se publican así, y cada
celular los descarga solo la próxima vez que abre la app:

```bash
npx eas-cli@latest update --channel preview --environment preview --message "Qué cambió"
```

- El canal `preview` llega a los APK generados con `--profile preview`, y `production` a los de Google Play.
- Si se agrega o cambia una librería con código nativo (`npx expo install ...`), la actualización no les
  llega a los APK viejos, porque el `runtimeVersion` usa la política `fingerprint`. En ese caso hay que
  generar un APK nuevo.
- Antes de publicar, probá los cambios con Expo Go.

## Publicar en Google Play

```bash
npx eas-cli@latest build --profile production --platform android
npx eas-cli@latest submit --platform android
```
