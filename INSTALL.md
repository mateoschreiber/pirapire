# Instalación de Pirapire

Guía de instalación standalone. Pirapire corre en un único contenedor Docker y
puede instalarse en cualquier carpeta.

## 1. Requisitos

- Docker Engine 20.10+ y Docker Compose v2 (`docker compose version`).
- Git.

Instalar Docker (si falta):
- Ubuntu: <https://docs.docker.com/engine/install/ubuntu/>
- Debian: <https://docs.docker.com/engine/install/debian/>

## 2. Obtener el proyecto

En cualquier carpeta del usuario:

```bash
git clone https://github.com/mateoschreiber/pirapire.git
cd pirapire
```

### Opcional: instalar en /opt

```bash
sudo mkdir -p /opt/pirapire
sudo chown -R "$USER:$USER" /opt/pirapire
git clone https://github.com/mateoschreiber/pirapire.git /opt/pirapire
cd /opt/pirapire
```

## 3. Configurar

```bash
cp .env.example .env
nano .env    # ajusta PIRAPIRE_PORT, APP_TIMEZONE, FOOTBALL_DATA_API_KEY (opcional)
```

## 4. Levantar

```bash
docker compose up -d --build
docker compose ps
curl http://localhost:8090/health
```

## 5. Comandos útiles

```bash
# Ver estado
docker compose ps

# Ver logs
docker compose logs -f pirapire_app

# Reiniciar
docker compose restart pirapire_app

# Detener
docker compose stop pirapire_app

# Detener y eliminar el contenedor (los datos en ./data se conservan)
docker compose down

# Reconstruir tras cambios de código
docker compose up -d --build pirapire_app
```

## 6. Verificar

Abre `http://localhost:8090/` (o `http://IP-DEL-EQUIPO:8090/` desde otra máquina de la LAN).
