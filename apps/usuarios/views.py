from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.db.models import F, Q
from django.utils import timezone
from datetime import timedelta

from apps.inventario.models import Producto
from apps.clientes.models import Cliente, Mascota
from apps.turnos.models import Turno
from apps.historia_clinica.models import RegistroVacuna
from .models import PerfilUsuario, Veterinaria, MensajeContacto, RegistroAuditoria, Plan, Suscripcion
from .forms import RegistroForm, ConfigVeterinariaForm
from .utils import get_veterinaria_activa


# ==============================================================================
# VISTAS PÚBLICAS Y LANDING PAGE
# ==============================================================================

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

    return render(request, 'landing.html')


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


class CustomLoginView(LoginView):
    """
    LoginView personalizado que verifica si el usuario fue aprobado por el superusuario.
    """
    template_name = 'usuarios/login.html'

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
    veterinaria = get_veterinaria_activa(request)
    hoy = timezone.now().date()
    limite_proximos = hoy + timedelta(days=15)

    if veterinaria:
        total_clientes = Cliente.objects.filter(veterinaria=veterinaria).count()
        total_mascotas = Mascota.objects.filter(cliente__veterinaria=veterinaria).count()

        productos_qs = Producto.objects.filter(veterinaria=veterinaria)
        total_productos = productos_qs.count()
        alertas_stock_qs = productos_qs.filter(stock_actual__lte=F('stock_minimo'))

        turnos_hoy_qs = Turno.objects.filter(veterinaria=veterinaria, fecha_hora__date=hoy)

        vacunas_alerta = RegistroVacuna.objects.filter(
            veterinaria=veterinaria,
            fecha_proxima_dosis__lte=limite_proximos
        ).select_related('mascota', 'mascota__cliente').order_by('fecha_proxima_dosis')[:5]

    elif request.user.is_superuser:
        total_clientes = Cliente.objects.count()
        total_mascotas = Mascota.objects.count()
        productos_qs = Producto.objects.all()
        total_productos = productos_qs.count()
        alertas_stock_qs = Producto.objects.filter(stock_actual__lte=F('stock_minimo'))
        turnos_hoy_qs = Turno.objects.filter(fecha_hora__date=hoy)
        vacunas_alerta = RegistroVacuna.objects.filter(
            fecha_proxima_dosis__lte=limite_proximos
        ).select_related('mascota', 'mascota__cliente').order_by('fecha_proxima_dosis')[:5]

    else:
        # Usuario autenticado sin veterinaria asignada: no debe ver datos de otros tenants.
        total_clientes = 0
        total_mascotas = 0
        productos_qs = Producto.objects.none()
        total_productos = 0
        alertas_stock_qs = Producto.objects.none()
        turnos_hoy_qs = Turno.objects.none()
        vacunas_alerta = RegistroVacuna.objects.none()

    turnos_totales = turnos_hoy_qs.count()
    turnos_pendientes = turnos_hoy_qs.filter(estado__in=['PENDIENTE', 'CONFIRMADO', 'EN_ESPERA']).count()
    turnos_completados = turnos_hoy_qs.filter(estado='COMPLETADO').count()

    context = {
        'veterinaria': veterinaria,
        'fecha_hoy': hoy,
        'total_clientes': total_clientes,
        'total_mascotas': total_mascotas,
        'total_productos': total_productos,
        'productos_bajo_stock': alertas_stock_qs.count(),
        'alertas_stock': alertas_stock_qs.select_related('categoria')[:5],
        'turnos_hoy_total': turnos_totales,
        'turnos_hoy_pendientes': turnos_pendientes,
        'turnos_hoy_completados': turnos_completados,
        'proximos_turnos': turnos_hoy_qs.select_related('mascota', 'veterinario').order_by('fecha_hora')[:5],
        'vacunas_alerta': vacunas_alerta,
    }
    return render(request, 'dashboard.html', context)


# ==============================================================================
# CONFIGURACIÓN / PERFIL DE VETERINARIA
# ==============================================================================

@login_required
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
    })


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
    """Extiende 30 días la suscripción y la marca como ACTIVA (registro manual de pago)."""
    if not request.user.is_superuser:
        messages.error(request, "No tenés permisos para esta acción.")
        return redirect('dashboard:index')

    suscripcion = get_object_or_404(Suscripcion, pk=suscripcion_id)

    if request.method == 'POST':
        base = suscripcion.fecha_vencimiento if suscripcion.fecha_vencimiento >= timezone.now().date() else timezone.now().date()
        suscripcion.fecha_vencimiento = base + timedelta(days=30)
        suscripcion.estado = 'ACTIVA'
        suscripcion.ultimo_pago_registrado = timezone.now().date()
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

    return render(request, 'usuarios/auditoria.html', {
        'registros': registros[:200],
        'acciones': RegistroAuditoria.ACCIONES,
        'accion_filtro': accion_filtro,
    })