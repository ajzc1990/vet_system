# VeterSystem móvil

App para el veterinario y el personal de la clínica (React Native + Expo SDK 57).
Usa la API REST de Django en `apps/api/` con login por token.

## Qué hace

- **Agenda:** turnos del día, con navegación entre días. Desde cada turno se puede confirmar, cancelar o atender (abre la consulta ya vinculada al turno).
- **Pacientes:** búsqueda por nombre de la mascota, tutor o DNI.
- **Ficha del paciente:** datos, tutor (llamar o WhatsApp), internación activa, resumen con IA, vacunas (marca las vencidas), consultas, recetas y desparasitaciones.
- **Altas:** nueva consulta con signos vitales, vacuna con atajos para la próxima dosis y receta con varios medicamentos.
  Solo las ven los roles VET y ADMIN, igual que en la web.

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

## Publicar en las tiendas

La app se compila en la nube con EAS, sin Android Studio ni Mac. Los perfiles de
[eas.json](eas.json) ya apuntan a `https://vetersystem.com`:

```bash
npx eas-cli@latest login
npx eas-cli@latest build --profile preview --platform android      # APK para instalar directo y probar
npx eas-cli@latest build --profile production --platform android   # .aab para Google Play
npx eas-cli@latest submit --platform android
```

Antes de compilar, el backend de producción tiene que tener los endpoints de `apps/api/`
de esta versión (por ejemplo `/api/yo/`). Si no, la app no puede iniciar sesión.
