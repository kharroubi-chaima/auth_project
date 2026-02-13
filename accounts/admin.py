from django.contrib import admin

from django.contrib import admin
from .models import User, Role, Permission, UserRole, RolePermission

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'first_name', 'last_name', 'status', 'is_staff')
    search_fields = ('email', 'first_name', 'last_name')

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'created_at')
    search_fields = ('name',)

@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'created_at')
    search_fields = ('name',)

admin.site.register(UserRole)
admin.site.register(RolePermission)