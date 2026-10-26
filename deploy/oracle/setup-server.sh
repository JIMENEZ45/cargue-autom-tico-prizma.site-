#!/usr/bin/env bash
# Prepara un servidor Ubuntu de Oracle Cloud para Auto Prizma Pro:
# instala Docker y abre los puertos 80 y 443 en el firewall del sistema.
# Ejecutar UNA vez, como el usuario "ubuntu":  bash setup-server.sh
# Ver docs/DEPLOY_ORACLE.md.
set -euo pipefail

echo "== Actualizando paquetes =="
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y git curl openssl iptables-persistent

echo "== Instalando Docker =="
if ! command -v docker >/dev/null 2>&1; then
    curl -fsSL https://get.docker.com | sudo sh
fi
sudo usermod -aG docker "$USER"

echo "== Abriendo puertos 80 y 443 =="
# Las imagenes Ubuntu de Oracle traen reglas iptables que rechazan todo salvo SSH.
# Las reglas nuevas se insertan antes del REJECT final.
for puerto in 80 443; do
    if ! sudo iptables -C INPUT -p tcp -m state --state NEW --dport "$puerto" -j ACCEPT 2>/dev/null; then
        sudo iptables -I INPUT 6 -p tcp -m state --state NEW --dport "$puerto" -j ACCEPT
    fi
done
sudo netfilter-persistent save

echo
echo "Listo. Cierra la sesion SSH y vuelve a entrar para usar docker sin sudo."
