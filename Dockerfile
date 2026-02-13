# Utiliser une image Python officielle
FROM python:3.13-slim

# Définir le répertoire de travail dans le conteneur
WORKDIR /app

# Copier le fichier des dépendances d'abord pour profiter du cache Docker
COPY requirements.txt .

# Installer les dépendances
RUN pip install --no-cache-dir -r requirements.txt

# Copier tout le code de l'application
COPY . .

# Exposer le port sur lequel Django tourne (par défaut 8000)
EXPOSE 8000

# Commande par défaut pour lancer le serveur
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]