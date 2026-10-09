import json

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from datetime import timedelta

from .models import PerfilUsuario, Veterinaria, MensajeContacto, RegistroAuditoria, Plan, Suscripcion
from .forms import RegistroForm, ConfigVeterinariaForm, CrearUsuarioEquipoForm
from .utils import get_veterinaria_activa
from .audit import registrar_auditoria
from .decorators import requerir_rol_admin
from .pagos import mp_configurado, crear_preferencia_pago, obtener_pago


# ==============================================================================
# VISTAS PÚBLICAS Y LANDING PAGE
# ==============================================================================

def _formato_pesos(valor):
    """Formatea un monto en pesos con punto de miles (ej. 20000 -> '20.000')."""
    return f"{int(valor):,}".replace(',', '.')


def landing_page(request):
    """Página de bienvenida pública con Misión, Visión, Objetivos y Formulario de Contacto que guarda en BD."""
    if request.user.is_authenticated:
        return redirect('dashboard:index')
    
    if request.method == 'POST':
        # Procesar y guardar formulario de contacto público en BD
        nombre = request.POST.get('nombre')
        email = request.POST.get('email')
        telefono = request.POST.get('telefono')
        veterinaria_nombre = request.POST.get('veterinaria') or request.POST.get('asunto')
        mensaje = request.POST.get('mensaje')

        if nombre and email and mensaje:
            MensajeContacto.objects.create(
                nombre=nombre,
                email=email,
                telefono=telefono,
                asunto=veterinaria_nombre,
                mensaje=mensaje
            )
            messages.success(
                request, 
                f"¡Gracias {nombre}! Hemos recibido tu consulta y fue registrada correctamente. Nos pondremos en contacto contigo a la brevedad."
            )
            return redirect('landing')
        else:
            messages.error(request, "Por favor completa los campos obligatorios (Nombre, Email y Mensaje).")

    plan_destacado = Plan.objects.filter(activo=True).order_by('orden', 'precio_mensual').first()
    ahorro_anual = None
    precio_mensual_fmt = precio_anual_fmt = ahorro_anual_fmt = None
    if plan_destacado:
        ahorro_anual = (plan_destacado.precio_mensual * 12) - plan_destacado.precio_anual
        precio_mensual_fmt = _formato_pesos(plan_destacado.precio_mensual)
        precio_anual_fmt = _formato_pesos(plan_destacado.precio_anual)
        ahorro_anual_fmt = _formato_pesos(ahorro_anual)

    return render(request, 'landing.html', {
        'plan_destacado': plan_destacado,
        'ahorro_anual': ahorro_anual,
        'precio_mensual_fmt': precio_mensual_fmt,
        'precio_anual_fmt': precio_anual_fmt,
        'ahorro_anual_fmt': ahorro_anual_fmt,
    })


def entrar_a_demo(request):
    """Acceso público de un solo clic a la demo en vivo: loguea directamente como el
    administrador de la veterinaria demo (creada por el comando seed_demo), sin pedirle
    usuario/clave a un prospecto. Es un entorno compartido entre todos los visitantes
    -no se crea un tenant nuevo por cada uno- que se resetea periódicamente corriendo
    'python manage.py seed_demo --reset' (por ejemplo, vía cron)."""
    from .management.commands.seed_demo import DEMO_VET_NOMBRE, DEMO_ADMIN_USERNAME

    if request.user.is_authenticated:
        logout(request)

    demo_admin = User.objects.filter(
        username=DEMO_ADMIN_USERNAME, perfil__veterinaria__nombre=DEMO_VET_NOMBRE,
    ).first()

    if not demo_admin:
        messages.error(
            request,
            "La demo en vivo no está disponible en este momento. Escribinos y te la mostramos personalmente."
        )
        return redirect('landing')

    login(request, demo_admin, backend='django.contrib.auth.backends.ModelBackend')
    messages.info(
        request,
        "Estás en un entorno de demostración compartido con datos de ejemplo: se reinicia "
        "periódicamente, así que no cargues información real."
    )
    return redirect('dashboard:index')


# ==============================================================================
# VISTAS DE AUTENTICACIÓN Y REGISTRO
# ==============================================================================

def registro(request):
    """
    Permite registrar un nuevo usuario en el sistema vinculándolo a una Veterinaria.
    El usuario queda registrado en estado PENDIENTE de aprobación por un superusuario.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = RegistroForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()

            PerfilUsuario.objects.create(
                user=user,
                veterinaria=form.cleaned_data['veterinaria'],
                rol=form.cleaned_data['rol'],
                telefono=form.cleaned_data.get('telefono', ''),
                is_approved=False  # Requiere aprobación del superusuario
            )

            messages.success(
                request, 
                "¡Solicitud de registro enviada con éxito! "
                "Tu cuenta se encuentra pendiente de aprobación por el superusuario para activar el acceso."
            )
            return redirect('login')
        else:
            messages.error(request, "Error al procesar el registro. Por favor revisa los datos ingresados.")
    else:
        form = RegistroForm()

    return render(request, 'usuarios/registro.html', {'form': form})


LOGIN_THROTTLE_MAX_INTENTOS = 5
LOGIN_THROTTLE_VENTANA_MINUTOS = 15


class CustomLoginView(LoginView):
    """
    LoginView personalizado que verifica si el usuario fue aprobado por el superusuario
    y bloquea temporalmente el acceso tras varios intentos fallidos (fuerza bruta).
    """
    template_name = 'usuarios/login.html'

    def post(self, request, *args, **kwargs):
        username = (request.POST.get('username') or '').strip()
        if username and self._demasiados_intentos_fallidos(username):
            messages.error(
                request,
                f"Demasiados intentos fallidos para el usuario '{username}'. "
                f"Por seguridad, esperá {LOGIN_THROTTLE_VENTANA_MINUTOS} minutos antes de volver a intentar."
            )
            return redirect('login')
        return super().post(request, *args, **kwargs)

    def _demasiados_intentos_fallidos(self, username):
        limite = timezone.now() - timedelta(minutes=LOGIN_THROTTLE_VENTANA_MINUTOS)
        intentos = RegistroAuditoria.objects.filter(
            accion='LOGIN_FALLIDO', objeto_id=username, fecha__gte=limite
        ).count()
        return intentos >= LOGIN_THROTTLE_MAX_INTENTOS

    def form_valid(self, form):
        user = form.get_user()

        # Superusuarios tienen libre acceso
        if user.is_superuser:
            return super().form_valid(form)

        # Los clientes con acceso al Portal (creado por el staff) no requieren
        # aprobación adicional: ya fueron validados al momento de crear el acceso.
        if hasattr(user, 'cliente_portal'):
            return super().form_valid(form)

        # Control de aprobación para usuarios normales (staff de la veterinaria)
        perfil = getattr(user, 'perfil', None)
        if not perfil or not perfil.is_approved:
            logout(self.request)
            messages.error(
                self.request,
                "Tu cuenta aún no ha sido aprobada por el administrador/superusuario. Intenta nuevamente más tarde."
            )
            return redirect('login')

        return super().form_valid(form)

    def get_success_url(self):
        if hasattr(self.request.user, 'cliente_portal'):
            return reverse('portal:home')
        return super().get_success_url()


# ==============================================================================
# DASHBOARD
# ==============================================================================

@login_required
def dashboard(request):
    """Alias histórico: el panel operativo real vive en dashboard:index
    (apps.dashboard). Se conserva esta URL solo para no romper enlaces viejos."""
    return redirect('dashboard:index')


# ==============================================================================
# CONFIGURACIÓN / PERFIL DE VETERINARIA
# ==============================================================================

@login_required
@requerir_rol_admin
def configurar_veterinaria(request):
    """Permite configurar y actualizar el perfil, logo y datos de contacto de la clínica."""
    vet = get_veterinaria_activa(request)
    
    if not vet:
        messages.error(request, "No tienes una veterinaria asociada para configurar.")
        return redirect('dashboard')

    if request.method == 'POST':
        form = ConfigVeterinariaForm(request.POST, request.FILES, instance=vet)
        if form.is_valid():
            form.save()
            messages.success(request, "Los datos de la veterinaria se actualizaron correctamente.")
            return redirect('usuarios:configurar_veterinaria')
        else:
            messages.error(request, "Error al guardar los datos. Por favor revisa el formulario.")
    else:
        form = ConfigVeterinariaForm(instance=vet)

    return render(request, 'usuarios/config_veterinaria.html', {'form': form, 'veterinaria': vet})


# ==============================================================================
# SUSCRIPCIONES / BILLING
# ==============================================================================

@login_required
@requerir_rol_admin
def mi_suscripcion(request):
    """Muestra a la veterinaria activa el estado de su propia suscripción/plan contratado."""
    vet = get_veterinaria_activa(request)

    if not vet:
        messages.error(request, "No tenés una veterinaria asociada para consultar la suscripción.")
        return redirect('dashboard:index')

    suscripcion = getattr(vet, 'suscripcion', None)
    return render(request, 'usuarios/mi_suscripcion.html', {
        'veterinaria': vet,
        'suscripcion': suscripcion,
        'mp_configurado': mp_configurado(),
        'pago': request.GET.get('pago'),
    })


@login_required
@requerir_rol_admin
def iniciar_pago_suscripcion(request):
    """Redirige al Checkout Pro de Mercado Pago para pagar el plan contratado, en el
    ciclo elegido (?ciclo=MENSUAL o ANUAL; por defecto el ciclo actual de la suscripción)."""
    vet = get_veterinaria_activa(request)
    suscripcion = getattr(vet, 'suscripcion', None) if vet else None

    if not suscripcion:
        messages.error(request, "No se encontró una suscripción para procesar el pago.")
        return redirect('usuarios:mi_suscripcion')

    if not mp_configurado():
        messages.warning(
            request,
            "Los pagos online todavía no están configurados. Contactá al equipo de VeterSystem para coordinar el pago."
        )
        return redirect('usuarios:mi_suscripcion')

    ciclo = request.GET.get('ciclo')
    ciclo = ciclo if ciclo in ('MENSUAL', 'ANUAL') else None

    try:
        preferencia = crear_preferencia_pago(suscripcion, request, ciclo=ciclo)
    except Exception:
        messages.error(request, "No se pudo iniciar el pago en este momento. Intentá nuevamente más tarde.")
        return redirect('usuarios:mi_suscripcion')

    init_point = preferencia.get('init_point') or preferencia.get('sandbox_init_point')
    if not init_point:
        messages.error(request, "No se pudo iniciar el pago en este momento.")
        return redirect('usuarios:mi_suscripcion')

    return redirect(init_point)


@csrf_exempt
def webhook_mercadopago(request):
    """Notificación de pago de Mercado Pago (IPN clásica por querystring o Webhooks v2 por
    JSON). Si el pago está aprobado, extiende 30 días la Suscripcion referenciada."""
    topic = request.GET.get('type') or request.GET.get('topic')
    payment_id = request.GET.get('data.id') or request.GET.get('id')

    if not payment_id and request.method == 'POST' and request.body:
        try:
            body = json.loads(request.body)
            topic = topic or body.get('type') or body.get('action', '').split('.')[0]
            payment_id = payment_id or (body.get('data') or {}).get('id')
        except (ValueError, TypeError):
            pass

    if not payment_id or (topic and topic != 'payment') or not mp_configurado():
        return HttpResponse(status=200)

    try:
        pago = obtener_pago(payment_id)
    except Exception:
        return HttpResponse(status=200)

    if pago.get('status') == 'approved':
        suscripcion = Suscripcion.objects.filter(pk=pago.get('external_reference')).select_related('veterinaria').first()
        if suscripcion:
            ciclo = str((pago.get('metadata') or {}).get('ciclo', 'MENSUAL')).upper()
            dias = 365 if ciclo == 'ANUAL' else 30

            hoy = timezone.localdate()
            base = suscripcion.fecha_vencimiento if suscripcion.fecha_vencimiento >= hoy else hoy
            suscripcion.fecha_vencimiento = base + timedelta(days=dias)
            suscripcion.ciclo_facturacion = ciclo if ciclo in ('MENSUAL', 'ANUAL') else 'MENSUAL'
            suscripcion.estado = 'ACTIVA'
            suscripcion.ultimo_pago_registrado = hoy
            suscripcion.save()

            registrar_auditoria(
                None, 'EDITAR', modelo='Suscripcion', objeto_id=suscripcion.id,
                descripcion=(
                    f"Pago aprobado vía Mercado Pago (payment_id={payment_id}, ciclo={ciclo}). "
                    f"Suscripción extendida hasta {suscripcion.fecha_vencimiento.strftime('%d/%m/%Y')}."
                ),
                veterinaria=suscripcion.veterinaria,
            )

    return HttpResponse(status=200)


@login_required
def panel_suscripciones(request):
    """Panel de gestión de suscripciones de todos los tenants, solo para superusuarios."""
    if not request.user.is_superuser:
        messages.error(request, "No tenés permisos para acceder al panel de suscripciones.")
        return redirect('dashboard:index')

    suscripciones = Suscripcion.objects.select_related('veterinaria', 'plan').all()
    veterinarias_sin_suscripcion = Veterinaria.objects.filter(suscripcion__isnull=True)

    return render(request, 'usuarios/panel_suscripciones.html', {
        'suscripciones': suscripciones,
        'veterinarias_sin_suscripcion': veterinarias_sin_suscripcion,
    })


@login_required
def extender_suscripcion(request, suscripcion_id):
    """Extiende la suscripción (30 o 365 días según el ciclo elegido) y la marca como
    ACTIVA (registro manual de un pago coordinado fuera de Mercado Pago)."""
    if not request.user.is_superuser:
        messages.error(request, "No tenés permisos para esta acción.")
        return redirect('dashboard:index')

    suscripcion = get_object_or_404(Suscripcion, pk=suscripcion_id)

    if request.method == 'POST':
        ciclo = request.POST.get('ciclo')
        ciclo = ciclo if ciclo in ('MENSUAL', 'ANUAL') else 'MENSUAL'
        dias = 365 if ciclo == 'ANUAL' else 30

        hoy = timezone.localdate()
        base = suscripcion.fecha_vencimiento if suscripcion.fecha_vencimiento >= hoy else hoy
        suscripcion.fecha_vencimiento = base + timedelta(days=dias)
        suscripcion.ciclo_facturacion = ciclo
        suscripcion.estado = 'ACTIVA'
        suscripcion.ultimo_pago_registrado = hoy
        suscripcion.save()

        messages.success(request, f"Suscripción de {suscripcion.veterinaria.nombre} extendida hasta el {suscripcion.fecha_vencimiento.strftime('%d/%m/%Y')}.")

    return redirect('usuarios:panel_suscripciones')


# ==============================================================================
# AUDITORÍA
# ==============================================================================

@login_required
def auditoria_view(request):
    """Bitácora de acciones relevantes del sistema. Un ADMIN de veterinaria solo ve
    los eventos de su propio tenant; el superusuario ve todo el sistema."""
    vet = get_veterinaria_activa(request)

    if request.user.is_superuser:
        registros = RegistroAuditoria.objects.select_related('usuario', 'veterinaria').all()
    elif vet and getattr(request.user, 'perfil', None) and request.user.perfil.rol == 'ADMIN':
        registros = RegistroAuditoria.objects.filter(veterinaria=vet).select_related('usuario', 'veterinaria')
    else:
        messages.error(request, "Solo el administrador de la veterinaria puede consultar la auditoría.")
        return redirect('dashboard:index')

    accion_filtro = request.GET.get('accion')
    if accion_filtro:
        registros = registros.filter(accion=accion_filtro)

    # En la veterinaria demo pública no mostramos IPs ni usuarios reales: cualquiera
    # que entra a probar el sistema cae en este mismo tenant compartido y vería datos
    # de otros visitantes (y de pruebas internas) que no le corresponden.
    from .management.commands.seed_demo import DEMO_VET_NOMBRE
    ocultar_datos_sensibles = bool(vet and vet.nombre == DEMO_VET_NOMBRE)

    return render(request, 'usuarios/auditoria.html', {
        'registros': registros[:200],
        'acciones': RegistroAuditoria.ACCIONES,
        'accion_filtro': accion_filtro,
        'ocultar_datos_sensibles': ocultar_datos_sensibles,
    })


# ==============================================================================
# GESTIÓN DE EQUIPO
# ==============================================================================

def _crear_veterinario_para_perfil(user, vet, matricula=''):
    """Crea la ficha de Veterinario (turnos.Veterinario) para un usuario con rol VET que
    todavía no tiene una, para que aparezca en el desplegable al asignar turnos/consultas.
    Si no se indica matrícula, usa un valor provisorio que se puede corregir después desde
    la pantalla de Veterinarios."""
    from apps.turnos.models import Veterinario
    if Veterinario.objects.filter(usuario=user).exists():
        return
    Veterinario.objects.create(
        veterinaria=vet,
        usuario=user,
        nombre=user.first_name or user.username,
        apellido=user.last_name or '',
        matricula=matricula or f"PENDIENTE-{user.id}",
        telefono=getattr(getattr(user, 'perfil', None), 'telefono', '') or '',
        email=user.email,
        activo=True,
    )


@login_required
@requerir_rol_admin
def gestionar_equipo(request):
    """Permite al ADMIN de una veterinaria sumar, aprobar, cambiar el rol o revocar el
    acceso de su propio equipo, sin depender de que el superusuario lo haga a mano
    desde el Django admin."""
    vet = get_veterinaria_activa(request)
    if not vet:
        messages.error(request, "No tenés una veterinaria activa para gestionar el equipo.")
        return redirect('dashboard:index')

    if request.method == 'POST':
        accion = request.POST.get('accion')

        if accion == 'crear':
            form = CrearUsuarioEquipoForm(request.POST, veterinaria=vet)
            if form.is_valid():
                nuevo_usuario = form.save(commit=False)
                nuevo_usuario.set_password(form.cleaned_data['password'])
                nuevo_usuario.save()

                PerfilUsuario.objects.create(
                    user=nuevo_usuario,
                    veterinaria=vet,
                    rol=form.cleaned_data['rol'],
                    telefono=form.cleaned_data.get('telefono', ''),
                    is_approved=True,
                )
                if form.cleaned_data['rol'] == 'VET':
                    _crear_veterinario_para_perfil(nuevo_usuario, vet, form.cleaned_data.get('matricula', ''))
                registrar_auditoria(
                    request, 'CREAR', modelo='PerfilUsuario', objeto_id=nuevo_usuario.id,
                    descripcion=f"'{nuevo_usuario.username}' agregado al equipo de {vet.nombre}.",
                )
                messages.success(request, f"'{nuevo_usuario.username}' fue agregado al equipo correctamente.")
                return redirect('usuarios:gestionar_equipo')

            miembros = PerfilUsuario.objects.filter(veterinaria=vet).select_related('user').order_by('is_approved', 'user__username')
            messages.error(request, "Revisá los datos del nuevo integrante.")
            return render(request, 'usuarios/gestionar_equipo.html', {
                'miembros': miembros, 'form_nuevo': form, 'veterinaria': vet, 'roles': PerfilUsuario.ROLES,
            })

        perfil = get_object_or_404(PerfilUsuario, pk=request.POST.get('perfil_id'), veterinaria=vet)
        if perfil.user_id == request.user.id:
            messages.error(request, "No podés modificar tu propio acceso desde esta pantalla.")
            return redirect('usuarios:gestionar_equipo')

        if accion == 'aprobar':
            perfil.is_approved = True
            perfil.save()
            if perfil.rol == 'VET':
                _crear_veterinario_para_perfil(perfil.user, vet)
            messages.success(request, f"Acceso aprobado para '{perfil.user.username}'.")
        elif accion == 'revocar':
            perfil.is_approved = False
            perfil.save()
            messages.success(request, f"Acceso revocado para '{perfil.user.username}'.")
        elif accion == 'cambiar_rol':
            nuevo_rol = request.POST.get('rol')
            if nuevo_rol in dict(PerfilUsuario.ROLES):
                perfil.rol = nuevo_rol
                perfil.save()
                if nuevo_rol == 'VET':
                    _crear_veterinario_para_perfil(perfil.user, vet)
                messages.success(request, f"Rol de '{perfil.user.username}' actualizado a {perfil.get_rol_display()}.")
        elif accion == 'rechazar':
            username = perfil.user.username
            perfil.user.delete()  # cascada borra el PerfilUsuario
            messages.success(request, f"Solicitud de '{username}' rechazada.")

        registrar_auditoria(
            request, 'EDITAR', modelo='PerfilUsuario', objeto_id=perfil.pk if accion != 'rechazar' else None,
            descripcion=f"Gestión de equipo en {vet.nombre}: acción '{accion}' sobre usuario del equipo.",
        )
        return redirect('usuarios:gestionar_equipo')

    miembros = PerfilUsuario.objects.filter(veterinaria=vet).select_related('user').order_by('is_approved', 'user__username')
    return render(request, 'usuarios/gestionar_equipo.html', {
        'miembros': miembros,
        'form_nuevo': CrearUsuarioEquipoForm(),
        'veterinaria': vet,
        'roles': PerfilUsuario.ROLES,
    })