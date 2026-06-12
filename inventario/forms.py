from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import Group, User
from django.db.models import Q
from .models import Categoria, MovimientoInventario, Proveedor, Producto


class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ['nombre', 'descripcion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = ['nombre', 'contacto', 'telefono', 'email']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'contacto': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = [
            'sku', 'nombre', 'categoria', 'stock_minimo', 'unidad', 'lote', 'fecha_vencimiento',
            'ubicacion_categoria', 'ubicacion', 'activo', 'precio', 'vendedor'
        ]
        widgets = {
            'sku': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. PROD-001'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'stock_minimo': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'unidad': forms.Select(attrs={'class': 'form-select'}),
            'lote': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. L-2026-01'}),
            'fecha_vencimiento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'ubicacion_categoria': forms.Select(attrs={'class': 'form-select'}),
            'ubicacion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Estante 2, torre B, cajon 4'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'precio': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'vendedor': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean_sku(self):
        sku = self.cleaned_data.get('sku')
        return sku.strip().upper() if sku else None


class TrasladoUbicacionForm(forms.Form):
    ubicacion_categoria = forms.ChoiceField(choices=Producto.UBICACION_CATEGORIA_CHOICES, required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    ubicacion = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nuevo detalle de ubicacion'}))
    motivo = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Motivo del traslado'}))


ROL_CHOICES = [
    ('Administrador', 'Administrador'),
    ('Operador', 'Operador'),
    ('Consulta', 'Consulta'),
]


def rol_a_grupo(nombre_rol):
    return Group.objects.filter(name=nombre_rol).first()


class UsuarioAdminCreateForm(UserCreationForm):
    rol = forms.ChoiceField(
        choices=ROL_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Rol',
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'rol', 'is_active')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.is_active = self.cleaned_data.get('is_active', True)
        rol = self.cleaned_data['rol']
        if commit:
            user.save()
            user.groups.clear()
            grupo = rol_a_grupo(rol)
            if grupo:
                user.groups.add(grupo)
            user.is_staff = rol == 'Administrador'
            user.is_superuser = rol == 'Administrador'
            user.save(update_fields=['is_staff', 'is_superuser'])
        return user


class UsuarioAdminUpdateForm(forms.ModelForm):
    password1 = forms.CharField(
        label='Nueva contraseña',
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )
    password2 = forms.CharField(
        label='Confirmar nueva contraseña',
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )
    rol = forms.ChoiceField(
        choices=ROL_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Rol',
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'rol', 'is_active')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['rol'].initial = self.obtener_rol_actual()

    def obtener_rol_actual(self):
        nombres = set(self.instance.groups.values_list('name', flat=True))
        if 'Administrador' in nombres:
            return 'Administrador'
        if 'Operador' in nombres:
            return 'Operador'
        if 'Consulta' in nombres:
            return 'Consulta'
        if self.instance.is_superuser:
            return 'Administrador'
        return 'Consulta'

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        if password1 or password2:
            if password1 != password2:
                raise forms.ValidationError('Las contraseñas no coinciden.')
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        rol = self.cleaned_data['rol']
        if commit:
            user.save()
            user.groups.clear()
            grupo = rol_a_grupo(rol)
            if grupo:
                user.groups.add(grupo)
            user.is_staff = rol == 'Administrador'
            user.is_superuser = rol == 'Administrador'
            user.save(update_fields=['is_staff', 'is_superuser'])
            password = self.cleaned_data.get('password1')
            if password:
                user.set_password(password)
                user.save(update_fields=['password'])
        return user


class UsuarioLoginForm(AuthenticationForm):
    username = forms.CharField(
        label='Usuario o correo',
        widget=forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}),
    )
    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username and password:
            UserModel = get_user_model()
            lookup = Q(username__iexact=username) | Q(email__iexact=username)
            try:
                user_obj = UserModel.objects.get(lookup)
                username = user_obj.get_username()
            except UserModel.DoesNotExist:
                pass

            self.user_cache = authenticate(self.request, username=username, password=password)
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data


class MovimientoForm(forms.ModelForm):
    class Meta:
        model = MovimientoInventario
        fields = ['producto', 'cantidad', 'tipo', 'motivo']
        widgets = {
            'producto': forms.Select(attrs={'class': 'form-select'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'motivo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Compra, venta, ajuste, devolucion'}),
        }
