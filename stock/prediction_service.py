import pandas as pd
import numpy as np
try:
    from prophet import Prophet
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning("Prophet library not found. Using DummyProphet fallback.")
    class DummyProphet:
        def __init__(self, *args, **kwargs):
            pass
        def fit(self, df):
            self.df = df
        def make_future_dataframe(self, periods):
            import pandas as pd
            future_dates = pd.date_range(start=self.df['ds'].iloc[-1] + pd.Timedelta(days=1), periods=periods)
            return pd.DataFrame({'ds': future_dates})
        def predict(self, future):
            import pandas as pd, numpy as np
            future = future.copy()
            # Simple average forecast
            avg = self.df['y'].mean() if not self.df.empty else 0
            future['yhat'] = avg
            return future
    Prophet = DummyProphet

from django.db import models
from django.db.models import Sum, F
from django.db import models
from django.db.models import Sum, F
from django.utils import timezone
from datetime import timedelta
from .models import LigneVente, StockPharmacie, Medicament
import logging

logger = logging.getLogger(__name__)

class StockPredictionService:
    @staticmethod
    def predict_stockout(medicament_id, pharmacie_id=None, horizon_days=30):
        """
        Prédit la date de rupture de stock pour un médicament donné.
        """
        try:
            # 1. Récupérer l'historique des ventes quotidiennes
            filters = {'medicament_id': medicament_id}
            if pharmacie_id:
                filters['vente__pharmacie_id'] = pharmacie_id
            
            # On prend les 90 derniers jours pour avoir une tendance
            start_date = timezone.now() - timedelta(days=90)
            ventes_qs = LigneVente.objects.filter(
                **filters,
                vente__created_at__gte=start_date
            ).values('vente__created_at__date').annotate(
                total_vendu=Sum('quantite')
            ).order_by('vente__created_at__date')

            if not ventes_qs or len(ventes_qs) < 3:
                return {"error": "Pas assez de données historiques pour ce médicament (min 3 jours)"}

            # 2. Préparer le DataFrame pour Prophet
            data = []
            for v in ventes_qs:
                data.append({
                    'ds': v['vente__created_at__date'],
                    'y': v['total_vendu']
                })
            
            df = pd.DataFrame(data)
            df['ds'] = pd.to_datetime(df['ds'])

            # 3. Initialiser et entraîner le modèle Prophet
            # On désactive les composants inutiles pour la performance
            m = Prophet(
                yearly_seasonality=False,
                weekly_seasonality=True,
                daily_seasonality=False,
                interval_width=0.8
            )
            m.fit(df)

            # 4. Prévision de la consommation future
            future = m.make_future_dataframe(periods=horizon_days)
            forecast = m.predict(future)

            # 5. Calculer la date de rupture basée sur le stock actuel
            # Récupérer le stock total (ou par pharmacie)
            if pharmacie_id:
                stock_obj = StockPharmacie.objects.filter(medicament_id=medicament_id, pharmacie_id=pharmacie_id).first()
                current_stock = stock_obj.quantite_stock if stock_obj else 0
            else:
                # Si global, on somme les stocks de toutes les pharmacies
                current_stock = StockPharmacie.objects.filter(medicament_id=medicament_id).aggregate(total=Sum('quantite_stock'))['total'] or 0

            # On itère sur les jours futurs pour soustraire la consommation prévue
            forecast_future = forecast[forecast['ds'] > pd.Timestamp(timezone.now().date())]
            
            remaining_stock = current_stock
            stockout_date = None
            
            for index, row in forecast_future.iterrows():
                # On utilise yhat (la prévision moyenne)
                daily_consumption = max(0, row['yhat'])
                remaining_stock -= daily_consumption
                
                if remaining_stock <= 0:
                    stockout_date = row['ds'].date()
                    break

            # Calculer la tendance (moyenne de consommation prévue)
            avg_daily_forecast = forecast_future['yhat'].mean()
            if pd.isna(avg_daily_forecast):
                avg_daily_forecast = 0.0

            return {
                "medicament_id": medicament_id,
                "current_stock": current_stock,
                "avg_daily_consumption": float(round(avg_daily_forecast, 2)),
                "stockout_date": stockout_date,
                "days_until_stockout": (stockout_date - timezone.now().date()).days if stockout_date else None,
                "is_critical": (stockout_date - timezone.now().date()).days < 7 if stockout_date else False
            }

        except Exception as e:
            logger.error(f"Erreur lors de la prédiction pour le médicament {medicament_id}: {str(e)}")
            return {"error": str(e)}

    @staticmethod
    def get_critical_predictions(pharmacie_id=None):
        """
        Scanne les médicaments avec un stock faible et génère des prédictions.
        """
        import concurrent.futures

        # On cible les médicaments qui ont déjà des alertes de stock faible
        if pharmacie_id:
            critical_stocks = StockPharmacie.objects.filter(
                pharmacie_id=pharmacie_id,
                quantite_stock__lte=F('seuil_alerte') * 3
            ).select_related('medicament', 'pharmacie')
        else:
            # Version SuperAdmin (global)
            critical_stocks = StockPharmacie.objects.filter(
                quantite_stock__lte=200
            ).select_related('medicament', 'pharmacie')

        predictions = []
        # On limite aux 10 plus critiques pour éviter de surcharger (au lieu de 15)
        stocks_to_analyze = list(critical_stocks[:10])
        
        def analyze_stock(s):
            # Forcer l'utilisation de s.pharmacie_id si pharmacie_id global n'est pas passé
            # Cela garantit qu'on calcule toujours le stock spécifique à la pharmacie de l'alerte
            target_pharmacie_id = pharmacie_id if pharmacie_id else s.pharmacie_id
            
            pred = StockPredictionService.predict_stockout(s.medicament_id, target_pharmacie_id)
            if "error" not in pred:
                pred['medicament_nom'] = s.medicament.nom
                # On force toujours l'affichage du nom de la pharmacie pour lever le doute
                pred['pharmacie_nom'] = s.pharmacie.nom
                return pred
            return None

        # Parallélisation pour accélérer grandement Prophet
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            results = executor.map(analyze_stock, stocks_to_analyze)
            
        for r in results:
            if r:
                predictions.append(r)
        
        return predictions
