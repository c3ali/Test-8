FROM python:3.12-slim

# Installer Node.js 20.x dans l'image Python
RUN apt-get update && apt-get install -y curl gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copier et installer les dépendances frontend
COPY package*.json ./
RUN npm install

# Copier et installer les dépendances backend
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copier tout le code
COPY . .

# Build du frontend (génère dist/)
RUN npm run build

# Exposer le port
EXPOSE 8080

# Démarrer uniquement le backend (qui servira le frontend statique)
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
