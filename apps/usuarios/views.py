from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.db.models import F, Q
from django.utils import timezone
from datetime import timedelta

from apps.inventario.models import Producto
from apps.clientes.models import Cliente, Mascota
from apps.turnos.models import Turno
from apps.historia_clinica.models import RegistroVacuna
from .models import PerfilUsuario, Veterinaria, MensajeContacto
from .forms import RegistroForm, ConfigVeterinariaForm


def _get_veterinaria(request):
    """Auxiliar robusto para obtener la veterinaria activa."""
    if hasattr(request, 'veterinaria') and request.veterinaria:
        return request.veterinaria
    if hasattr(request.user, 'perfil') and request.user.perfil and hasattr(request.user.perfil, 'veterinaria'):
        if request.user.perfil.veterinaria:
            return request.user.perfil.veterinaria
    if hasattr(request.user, 'veterinaria') and request.user.veterinaria:
        return request.user.veterinaria
    try:
        return Veterinaria.objects.first()
    except (ImportError, Exception):
        pass
    return None


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
    template_name = 'registration/login.html'

    def form_valid(self, form):
        user = form.get_user()
        
        # Superusuarios tienen libre acceso
        if user.is_superuser:
            return super().form_valid(form)

        # Control de aprobación para usuarios normales
        perfil = getattr(user, 'perfil', None)
        if not perfil or not perfil.is_approved:
            logout(self.request)
            messages.error(
                self.request, 
                "Tu cuenta aún no ha sido aprobada por el administrador/superusuario. Intenta nuevamente más tarde."
            )
            return redirect('login')

        return super().form_valid(form)


# ==============================================================================
# DASHBOARD
# ==============================================================================

@login_required
def dashboard(request):
    veterinaria = _get_veterinaria(request)
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

    else:
        total_clientes = Cliente.objects.count()
        total_mascotas = Mascota.objects.count()
        productos_qs = Producto.objects.all()
        total_productos = productos_qs.count()
        alertas_stock_qs = Producto.objects.filter(stock_actual__lte=F('stock_minimo'))
        turnos_hoy_qs = Turno.objects.filter(fecha_hora__date=hoy)
        vacunas_alerta = RegistroVacuna.objects.filter(
            fecha_proxima_dosis__lte=limite_proximos
        ).select_related('mascota', 'mascota__cliente').order_by('fecha_proxima_dosis')[:5]

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
    vet = _get_veterinaria(request)
    
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