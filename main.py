import network
import time
import json
import machine
import senko  
import ntptime  # NIEUW: Nodig om de netwerktijd op te halen
from machine import Pin
from umqtt.simple import MQTTClient

# --- CONFIGURATIE ---
ssid = "Postema 2.4G"
password = "Jard@Postema"

MQTT_BROKER   = "192.168.1.217"  
MQTT_USER     = "mqttuser"
MQTT_PASSWORD = "tggakcNwpX!6ptf"
CLIENT_ID     = "pico2w_01"

# GitHub gegevens voor de draadloze updates
GITHUB_USER = "Pjotterx"  
GITHUB_REPO = "pico2w_01_code"              

# Home Assistant Topics
DISCOVERY_LED = b"homeassistant/light/pico2w_01_led/config"
TOPIC_LED_STATE = b"pico2w_01/led/state"
TOPIC_LED_CMD   = b"pico2w_01/led/set"

DISCOVERY_RESTART = b"homeassistant/button/pico2w_01_restart/config"
TOPIC_RESTART_CMD   = b"pico2w_01/restart/set"

led = Pin("LED", Pin.OUT)
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

# --- Wi-Fi verbinding ---
if wlan.isconnected():
    print("Oude Wi-Fi verbinding resetten...")
    wlan.disconnect()
    time.sleep(1)

print("Verbinden met WiFi...")
wlan.connect(ssid, password)

timeout = 30
while timeout > 0:
    if wlan.isconnected(): 
        break
    led.toggle()
    time.sleep(0.5)
    timeout -= 1

if wlan.isconnected():
    led.on()
    print("Verbonden met Wi-Fi!")
    
    ip, mask, gateway, dns = wlan.ifconfig()
    print(f"Netwerkgegevens -> IP: {ip} | Gateway: {gateway} | Oude DNS: {dns}")
    
    wlan.ifconfig((ip, mask, gateway, "8.8.8.8"))
    print("DNS succesvol ingesteld op 8.8.8.8!")
    time.sleep(2)
    
    # --- NIEUW: Synchroniseer de interne klok met internet ---
    try:
        print("Tijd synchroniseren via NTP...")
        ntptime.settime()
        print("Klok succesvol gelijkgezet! Huidige tijd:", time.localtime())
    except Exception as ntp_err:
        print("Tijd synchroniseren mislukt, GitHub certificaat kan weigeren:", ntp_err)
        
else:
    led.off()
    print("Wi-Fi verbinding mislukt! Herstarten...")
    time.sleep(5)
    machine.reset()


# --- DRAADLOZE UPDATE CHECK (OTA) ---
print("Controleren op updates via GitHub...")
OTA = senko.Senko(
    user=GITHUB_USER,
    repo=GITHUB_REPO,
    branch="main",     
    files=["main.py"]  
)

try:
    if OTA.update():
        print("Nieuwe update gevonden en gedownload! Pico start opnieuw op...")
        time.sleep(1)
        machine.reset()  
    else:
        print("Code is up-to-date. Geen update nodig.")
except Exception as e:
    print("Update check mislukt (Geen internet of GitHub fout):", e)


# --- MQTT Callback (Luisteren naar Home Assistant) ---
def mqtt_callback(topic, msg):
    if topic == TOPIC_LED_CMD:
        if msg == b"ON":
            led.on()
            client.publish(TOPIC_LED_STATE, b"ON", retain=True)
        elif msg == b"OFF":
            led.off()
            client.publish(TOPIC_LED_STATE, b"OFF", retain=True)
            
    elif topic == TOPIC_RESTART_CMD:
        if msg == b"PRESS":
            print("Herstart ontvangen van HA...")
            time.sleep(1)
            machine.reset()

# --- Verbinden met MQTT & Discovery ---
print("Verbinden met MQTT...")
client = MQTTClient(CLIENT_ID, MQTT_BROKER, user=MQTT_USER, password=MQTT_PASSWORD)
client.set_callback(mqtt_callback)

try:
    client.connect()
    
    shared_device = {
        "identifiers": ["pico2w_01_board"],
        "name": "Raspberry Pi Pico 2W (02)",  
        "model": "Pico 2 W",
        "manufacturer": "Raspberry Pi"
    }
    
    # LED aanmelden
    led_payload = {
        "name": "Ingebouwde LED",
        "unique_id": "pico2w_01_built_in_led",
        "state_topic": TOPIC_LED_STATE.decode(),
        "command_topic": TOPIC_LED_CMD.decode(),
        "payload_on": "ON",
        "payload_off": "OFF",
        "device": shared_device
    }
    client.publish(DISCOVERY_LED, json.dumps(led_payload), retain=True)

    # Herstart-knop aanmelden
    restart_payload = {
        "name": "Herstarten",
        "unique_id": "pico2w_01_restart_btn",
        "command_topic": TOPIC_RESTART_CMD.decode(),
        "payload_press": "PRESS",
        "device_class": "restart",
        "device": shared_device
    }
    client.publish(DISCOVERY_RESTART, json.dumps(restart_payload), retain=True)
    
    client.subscribe(TOPIC_LED_CMD)
    client.subscribe(TOPIC_RESTART_CMD)
    
    initial_state = b"ON" if led.value() else b"OFF"
    client.publish(TOPIC_LED_STATE, initial_state, retain=True)
    print("MQTT en Discovery actief!")

except Exception as e:
    print("MQTT Fout:", e)

# --- Hoofdprogramma ---
while True:
    try:
        client.check_msg()
        time.sleep(0.2)
    except Exception as e:
        print("Fout in hoofdprogramma, herstarten over 5s:", e)
        time.sleep(5)
        machine.reset()
