#!/bin/bash

# --- CARREGA CREDENCIALS (.env) ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"

if [ -f "$ROOT_DIR/.venv/bin/activate" ]; then
    # shellcheck source=/dev/null
    source "$ROOT_DIR/.venv/bin/activate"
fi

if [ -f "$ENV_FILE" ]; then
    # shellcheck source=/dev/null
    source "$ENV_FILE"
fi
TOKEN="${TELEGRAM_TOKEN:-}"
CHAT_ID="${TELEGRAM_CHAT_ID:-}"

# CPU Limits
LIMIT_AVIS=85
LIMIT_PANIC=92

# RAM Usage Limit (GB)
LIMIT_RAM_GB=29.0

# RAM Temperature Limits
LIMIT_RAM_TEMP_AVIS=70
LIMIT_RAM_TEMP_PANIC=80

# NVMe Temperature Limits
LIMIT_NVME_TEMP_AVIS=70
LIMIT_NVME_TEMP_PANIC=80

LOG_FILE="$HOME/seguretat_tfm.log"

send_telegram() {
    curl -s -X POST "https://api.telegram.org/bot$TOKEN/sendMessage" \
        -d chat_id="$CHAT_ID" \
        -d text="$1" > /dev/null
}

log_message() {
    local level="$1"
    local message="$2"
    local timestamp=$(date "+%Y-%m-%d %H:%M:%S")
    echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

# Assegurem que el fitxer de log existeix
touch "$LOG_FILE"

log_message "INFO" "Monitor de seguretat avançat (amb CPU, RAM i NVMe) activat."
log_message "INFO" "Vigilant CPU (Temp/Estat), RAM (Ús/Temp) i NVMe (Temp)..."
send_telegram "🚀 Monitor de seguretat avançat activat. Vigilant Ryzen 7 5700X3D, RAM (Ús/Temp) i SSD NVMe per al TFM..."

# Estat inicial per al monitoratge de processos
tournament_was_running=true
if pgrep -f "benchmark.py" > /dev/null; then
    tournament_was_running=true
else
    tournament_was_running=false
fi

while true; do
    # 1. Llegim la temperatura Tctl de la CPU
    TEMP=$(sensors k10temp-pci-00c3 2>/dev/null | grep Tctl | awk '{print $2}' | tr -d '+°C' | cut -d. -f1)
    
    # Si no es troba la CPU amb k10temp, provem genèric
    if [ -z "$TEMP" ]; then
        TEMP=$(sensors 2>/dev/null | grep -E '(temp1|Core 0)' | head -n 1 | awk '{print $2}' | tr -d '+°C' | cut -d. -f1)
    fi

    # 2. Llegim l'ús de la RAM
    RAM_USED_MB=$(free -m | grep Mem | awk '{print $3}')
    RAM_TOTAL_MB=$(free -m | grep Mem | awk '{print $2}')
    RAM_USED_GB=$(echo "scale=2; $RAM_USED_MB / 1024" | bc)
    RAM_PCT=$(echo "scale=1; ($RAM_USED_MB / $RAM_TOTAL_MB) * 100" | bc)

    # 3. Llegim les temperatures de la RAM (màxima dels sensors jc42) i de l'NVMe (Composite)
    RAM_TEMP=$(sensors 2>/dev/null | awk '/jc42/{flag=1; next} flag==1 && /temp1:/{print $2; flag=0}' | tr -d '+°C' | cut -d. -f1 | sort -nr | head -n 1)
    if [ -z "$RAM_TEMP" ]; then
        RAM_TEMP=0
    fi

    NVME_TEMP=$(sensors 2>/dev/null | awk '/nvme-/{flag=1; next} flag==1 && /Composite:/{print $2; flag=0}' | tr -d '+°C' | cut -d. -f1 | sort -nr | head -n 1)
    if [ -z "$NVME_TEMP" ]; then
        NVME_TEMP=0
    fi

    # 4. Comprovem si el procés del torneig està actiu
    TOURNAMENT_RUNNING=false
    if pgrep -f "benchmark.py" > /dev/null; then
        TOURNAMENT_RUNNING=true
    fi

    # Log estat actual cada 5 minuts (aproximadament 10 iteracions de 30s)
    if [ $(( (SECONDS / 30) % 10 )) -eq 0 ]; then
        log_message "STATUS" "CPU: ${TEMP}°C | RAM: ${RAM_USED_GB}GB / $(echo "scale=2; $RAM_TOTAL_MB / 1024" | bc)GB (${RAM_PCT}%) | RAM Temp: ${RAM_TEMP}°C | NVMe Temp: ${NVME_TEMP}°C | Tournament: ${TOURNAMENT_RUNNING}"
    fi

    # --- CONTROL DE TEMPERATURES CPU ---
    # CAS 1.1: EMERGÈNCIA CRÍTICA CPU (Apagat de seguretat)
    if [ -n "$TEMP" ] && [ "$TEMP" -ge "$LIMIT_PANIC" ]; then
        log_message "EMERGENCY" "CPU a $TEMP°C. Supera el límit crític ($LIMIT_PANIC°C). APAGANT PC."
        send_telegram "🚨 CRÍTIC TFM: La CPU ha arribat a $TEMP°C. APAGANT EL PC PER SEGURETAT."
        sleep 5
        poweroff || systemctl poweroff || sudo poweroff
        exit 1
    fi

    # CAS 1.2: AVÍS TEMPERATURA ALTA CPU
    if [ -n "$TEMP" ] && [ "$TEMP" -ge "$LIMIT_AVIS" ]; then
        log_message "WARNING" "CPU a $TEMP°C. Supera límit d'avís ($LIMIT_AVIS°C)."
        send_telegram "⚠️ ALERTA TFM: La CPU està a $TEMP°C. Revisa el procés i la ventilació!"
        sleep 900 # Espera 15 minuts abans de tornar a avisar
    fi

    # --- CONTROL DE TEMPERATURES RAM ---
    # CAS 1.3: EMERGÈNCIA CRÍTICA RAM TEMP (Apagat de seguretat)
    if [ "$RAM_TEMP" -ge "$LIMIT_RAM_TEMP_PANIC" ]; then
        log_message "EMERGENCY" "RAM a $RAM_TEMP°C. Supera el límit crític ($LIMIT_RAM_TEMP_PANIC°C). APAGANT PC."
        send_telegram "🚨 CRÍTIC TFM: La RAM ha arribat a $RAM_TEMP°C. APAGANT EL PC PER SEGURETAT."
        sleep 5
        poweroff || systemctl poweroff || sudo poweroff
        exit 1
    fi

    # CAS 1.4: AVÍS TEMPERATURA ALTA RAM
    if [ "$RAM_TEMP" -ge "$LIMIT_RAM_TEMP_AVIS" ]; then
        log_message "WARNING" "RAM a $RAM_TEMP°C. Supera límit d'avís ($LIMIT_RAM_TEMP_AVIS°C)."
        send_telegram "⚠️ ALERTA TFM: La RAM està a $RAM_TEMP°C. Revisa el flux d'aire de la caixa!"
        sleep 900
    fi

    # --- CONTROL DE TEMPERATURES NVMe ---
    # CAS 1.5: EMERGÈNCIA CRÍTICA NVMe TEMP (Apagat de seguretat)
    if [ "$NVME_TEMP" -ge "$LIMIT_NVME_TEMP_PANIC" ]; then
        log_message "EMERGENCY" "NVMe a $NVME_TEMP°C. Supera el límit crític ($LIMIT_NVME_TEMP_PANIC°C). APAGANT PC."
        send_telegram "🚨 CRÍTIC TFM: El disc NVMe ha arribat a $NVME_TEMP°C. APAGANT EL PC PER SEGURETAT."
        sleep 5
        poweroff || systemctl poweroff || sudo poweroff
        exit 1
    fi

    # CAS 1.6: AVÍS TEMPERATURA ALTA NVMe
    if [ "$NVME_TEMP" -ge "$LIMIT_NVME_TEMP_AVIS" ]; then
        log_message "WARNING" "NVMe a $NVME_TEMP°C. Supera límit d'avís ($LIMIT_NVME_TEMP_AVIS°C)."
        send_telegram "⚠️ ALERTA TFM: El disc NVMe està a $NVME_TEMP°C. Revisa la temperatura interna i dissipació!"
        sleep 900
    fi

    # --- CONTROL DE RAM (Ús) ---
    # CAS 2.1: MEMÒRIA A PROP DE SATURACIÓ (Evitar OOM)
    if (( $(echo "$RAM_USED_GB >= $LIMIT_RAM_GB" | bc -l) )); then
        log_message "WARNING" "RAM a prop de saturació: ${RAM_USED_GB}GB utilitzats (${RAM_PCT}%)."
        send_telegram "⚠️ ALERTA MEMÒRIA: L'ús de RAM és de ${RAM_USED_GB}GB (${RAM_PCT}%). A punt d'arribar al límit de seguretat ($LIMIT_RAM_GB GB)."
        sleep 900
    fi

    # --- CONTROL DE PROCESSOS ---
    # CAS 3.1: Torneig aturat (ha acabat o ha caigut)
    if [ "$TOURNAMENT_RUNNING" = false ] && [ "$tournament_was_running" = true ]; then
        log_message "INFO" "El procés del torneig ('benchmark.py') s'ha aturat."
        send_telegram "🔔 NOTIFICACIÓ TFM: El procés del torneig ('benchmark.py') s'ha aturat. Comprova si ha finalitzat correctament o si ha caigut."
        tournament_was_running=false
    fi

    # Si torna a començar
    if [ "$TOURNAMENT_RUNNING" = true ] && [ "$tournament_was_running" = false ]; then
        log_message "INFO" "El procés del torneig ('benchmark.py') s'ha tornat a iniciar."
        tournament_was_running=true
    fi

    sleep 30
done
