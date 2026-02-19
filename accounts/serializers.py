from rest_framework import serializers
from .models import User, Role, Permission, UserRole, RolePermission


# convertir les objets en JSON et vice versa (validation des données)

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email', 'password', 'status', 'date_joined', 'is_active', 'is_staff']
        read_only_fields = ['id', 'date_joined']

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data)
        user.set_password(password)  
        user.save()
        return user
    
# Partie ajouter pour la 2FA avec Google Authenticator
class TOTPSetupSerializer(serializers.Serializer):
    """Renvoie le secret et l'URI pour le QR code."""
    secret = serializers.CharField(read_only=True)
    uri = serializers.CharField(read_only=True)

class TOTPVerifySerializer(serializers.Serializer):
    code = serializers.CharField(max_length=6, min_length=6)
    # On peut aussi demander le mot de passe pour sécuriser l'activation
    password = serializers.CharField(write_only=True, required=False)

    def validate_code(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("Le code doit contenir uniquement des chiffres.")
        return value

class TOTPDisableSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)
    code = serializers.CharField(max_length=6, min_length=6, required=False)
#fin de la partie 2FA

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = '__all__'
        read_only_fields = ['id', 'created_at']

class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = '__all__'
        read_only_fields = ['id', 'created_at']

class UserRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRole
        fields = '__all__'

class RolePermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RolePermission
        fields = '__all__'