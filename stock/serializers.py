from rest_framework import serializers
from django.db import transaction
from django.apps import apps
from .models import ATC, Medicament, Categorie, MouvementStock, StockPharmacie, Vente, LigneVente


class CategorieSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Categorie
        fields = '__all__'


class MedicamentSerializer(serializers.ModelSerializer):
    categorie_nom  = serializers.CharField(source='categorie.nom', read_only=True)
    expire_bientot = serializers.SerializerMethodField()
    stock_faible   = serializers.SerializerMethodField()
    en_rupture     = serializers.SerializerMethodField()

    nom             = serializers.CharField()
    categorie       = serializers.PrimaryKeyRelatedField(queryset=Categorie.objects.all())
    prix_achat      = serializers.DecimalField(max_digits=10, decimal_places=3)
    prix_vente      = serializers.DecimalField(max_digits=10, decimal_places=3)
    date_expiration = serializers.DateField()
    quantite_stock  = serializers.SerializerMethodField()


    def get_expire_bientot(self, obj):
        from datetime import date, timedelta
        if not obj.date_expiration:
            return False
        return obj.date_expiration <= date.today() + timedelta(days=30)
    def get_stock_faible(self, obj):
        q = getattr(obj, 'quantite_stock_reel', None)
        if q is None:
            q = obj.quantite_stock
        return 0 < q <= obj.seuil_alerte 
    def get_en_rupture(self, obj):
        q = getattr(obj, 'quantite_stock_reel', None)
        if q is None:
            q = obj.quantite_stock
        return q == 0
    
    
    def get_quantite_stock(self, obj):
        val = getattr(obj, 'quantite_stock_reel', None)
        return val if val is not None else 0
    seuil_alerte    = serializers.IntegerField(min_value=0)
    dci             = serializers.CharField(allow_null=True, allow_blank=True, required=False)
    description     = serializers.CharField(allow_null=True, allow_blank=True, required=False)

    class Meta:
        model  = Medicament
        fields = [
            'id', 'nom', 'dci',
            'categorie', 'categorie_nom',
            'prix_achat', 'prix_vente',
            'date_expiration', 'ordonnance_requise',
            'description',
            'quantite_stock', 'seuil_alerte',
            'expire_bientot', 'stock_faible', 'en_rupture',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class StockPharmacieSerializer(serializers.ModelSerializer):
    medicament_nom     = serializers.CharField(source='medicament.nom',      read_only=True)
    pharmacie_nom      = serializers.CharField(source='pharmacie.nom',       read_only=True)
    stock_faible       = serializers.BooleanField(read_only=True)
    en_rupture         = serializers.BooleanField(read_only=True)
    nom                = serializers.CharField(source='medicament.nom',      read_only=True)
    dci                = serializers.CharField(source='medicament.dci',      read_only=True)
    date_expiration    = serializers.DateField(source='medicament.date_expiration', read_only=True)
    expire_bientot     = serializers.BooleanField(source='medicament.expire_bientot', read_only=True)
    categorie          = serializers.SerializerMethodField()
    categorie_nom      = serializers.CharField(source='medicament.categorie.nom', read_only=True, default='')
    ordonnance_requise = serializers.BooleanField(source='medicament.ordonnance_requise', read_only=True)

    class Meta:
        model  = StockPharmacie
        fields = [
            'id', 'pharmacie', 'pharmacie_nom',
            'medicament', 'medicament_nom',
            'quantite_stock', 'seuil_alerte', 'prix_vente',
            'stock_faible', 'en_rupture',
            'nom', 'dci', 'date_expiration', 'expire_bientot',
            'categorie', 'categorie_nom', 'ordonnance_requise',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_categorie(self, obj):
        return obj.medicament.categorie.id if obj.medicament.categorie else None


class MouvementStockSerializer(serializers.ModelSerializer):
    medicament_nom = serializers.CharField(source='stock.medicament.nom', read_only=True)
    pharmacie_nom  = serializers.CharField(source='stock.pharmacie.nom',  read_only=True)
    created_by_nom = serializers.SerializerMethodField()

    class Meta:
        model  = MouvementStock
        fields = [
            'id', 'stock', 'medicament_nom', 'pharmacie_nom',
            'type', 'quantite', 'motif',
            'created_by', 'created_by_nom', 'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'created_by']

    def get_created_by_nom(self, obj):
        if obj.created_by:
            return f"{obj.created_by.first_name} {obj.created_by.last_name}".strip()
        return None

    def validate(self, data):
        if data['type'] =='sortie' and data['quantite'] > data['stock'].quantite_stock:
            raise serializers.ValidationError(
                f"Stock insuffisant pour {data['stock'].medicament.nom}. "
                f"Disponible : {data['stock'].quantite_stock}"
            )
        return data
    
    def create(self, validated_data):
        mouvement = MouvementStock.objects.create(**validated_data)
        return mouvement



# ── Ventes ────────────────────────────────────────────────────────────────────

class LigneVenteSerializer(serializers.ModelSerializer):
    medicament_nom = serializers.CharField(source='medicament.nom', read_only=True)
    sous_total     = serializers.DecimalField(max_digits=12, decimal_places=3, read_only=True)

    class Meta:
        model  = LigneVente
        fields = ['id', 'medicament', 'medicament_nom', 'quantite', 'prix_unitaire', 'sous_total']
        read_only_fields = ['id']


class VenteSerializer(serializers.ModelSerializer):
    lignes         = LigneVenteSerializer(many=True)
    created_by_nom = serializers.SerializerMethodField()
    pharmacie_nom  = serializers.CharField(source='pharmacie.nom', read_only=True)

    class Meta:
        model  = Vente
        fields = [
            'id', 'pharmacie', 'pharmacie_nom',
            'lignes', 'total', 'note',
            'created_by', 'created_by_nom', 'created_at',
        ]
        read_only_fields = ['id', 'total', 'created_at', 'created_by', 'pharmacie']

    def get_created_by_nom(self, obj):
        if obj.created_by:
            return f"{obj.created_by.first_name} {obj.created_by.last_name}".strip()
        return None

    def validate_lignes(self, lignes):
        if not lignes:
            raise serializers.ValidationError("La vente doit contenir au moins un médicament.")
        return lignes

    @transaction.atomic
    def create(self, validated_data):
        lignes_data = validated_data.pop('lignes')
        user        = self.context['request'].user

        # Utilise apps.get_model pour éviter tout problème de related_name
        # et cherche directement par le champ proprietaire
        
        from pharmacies.models import Pharmacie  # Import direct pour éviter les problèmes de related_name  
        
        pharmacie = Pharmacie.objects.filter(proprietaire=user).first()

        if not pharmacie:
            pharmacie = user.pharmacies_travail.filter(est_active=True).first()  
            
        if not pharmacie:
            raise serializers.ValidationError(
                "Aucune pharmacie associée à cet utilisateur. "
                "Contactez un administrateur."
            )

        vente = Vente.objects.create(
            pharmacie  = pharmacie,
            created_by = user,
            note       = validated_data.get('note', ''),
        )

        total = 0
        for ligne_data in lignes_data:
            medicament    = ligne_data['medicament']
            quantite      = ligne_data['quantite']
            prix_unitaire = ligne_data.get('prix_unitaire', medicament.prix_vente)

            stock = StockPharmacie.objects.filter(
                pharmacie=pharmacie,
                medicament=medicament
            ).first()
            
            if not stock:
                raise serializers.ValidationError(
                    f"Le médicament {medicament.nom} n'est pas disponible dans votre pharmacie."
                )
            if stock.quantite_stock < quantite:
                raise serializers.ValidationError(
                    f"Stock insuffisant pour {medicament.nom}. "
                    f"Disponible : {stock.quantite_stock}"
                )
            
            stock.quantite_stock -= quantite
            stock.save(update_fields=['quantite_stock'])
            
            LigneVente.objects.create(
                vente         = vente,
                medicament    = medicament,
                quantite      = quantite,
                prix_unitaire = prix_unitaire,
            )
            total += quantite * prix_unitaire
            
        vente.total = total
        vente.save(update_fields=['total'])
        return vente
            
    
from .models import Medicament, Categorie, MouvementStock, StockPharmacie, Vente, Notification

class NotificationSerializer(serializers.ModelSerializer):
    pharmacie_nom  = serializers.CharField(source='pharmacie.nom',      read_only=True)
    medicament_nom = serializers.CharField(source='medicament.nom',     read_only=True)
    type_display   = serializers.CharField(source='get_type_display',   read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)

    class Meta:
        model  = Notification
        fields = [
            'id',
            'pharmacie', 'pharmacie_nom',
            'medicament', 'medicament_nom',
            'type', 'type_display',
            'message',
            'statut', 'statut_display',
            'destinataire',
            'created_at',
        ]
        read_only_fields = fields
        
        
# serializers.py
class ATCSerializer(serializers.ModelSerializer):
    categories = CategorieSerializer(many=True, read_only=True)

    class Meta:
        model  = ATC
        fields = ['id', 'nom', 'description', 'categories']