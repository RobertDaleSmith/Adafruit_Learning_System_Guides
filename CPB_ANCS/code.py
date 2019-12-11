"""
This demo shows the latest icons from a connected Apple device on a TFT Gizmo screen.

The A and B buttons on the CircuitPlayground Bluefruit can be used to scroll through all active
notifications. The screen's backlight will turn off after a certain number of seconds to save power.
New notifications or pressing the buttons should turn it back on.
"""

import time
import board
import digitalio
import displayio
import adafruit_ble
from adafruit_ble.advertising.standard import SolicitServicesAdvertisement
from adafruit_ble.services.apple import AppleNotificationService
from adafruit_gizmo import tft_gizmo
from audiocore import WaveFile
from audiopwmio import PWMAudioOut as AudioOut

# Enable the speaker
speaker_enable = digitalio.DigitalInOut(board.SPEAKER_ENABLE)
speaker_enable.direction = digitalio.Direction.OUTPUT
speaker_enable.value = True

audio = AudioOut(board.SPEAKER)

# This is a whitelist of apps to show notifications from.
APP_ICONS = {
    "com.tinyspeck.chatlyio": "/ancs_slack.bmp",
    "com.basecamp.bc3-ios": "/ancs_basecamp.bmp",
    "com.apple.MobileSMS": "/ancs_sms.bmp",
    "com.hammerandchisel.discord": "/ancs_discord.bmp",
    "com.apple.mobilecal": "/ancs_ical.bmp",
    "com.apple.mobilephone": "/ancs_phone.bmp"
}

BLACKLIST = []
DELAY_AFTER_PRESS = 15
DEBOUNCE = 0.1
DIM_TIMEOUT = 20   # Amount of timeout to turn off backlight
DIM_LEVEL = 0.05

a = digitalio.DigitalInOut(board.BUTTON_A)
a.switch_to_input(pull=digitalio.Pull.DOWN)
b = digitalio.DigitalInOut(board.BUTTON_B)
b.switch_to_input(pull=digitalio.Pull.DOWN)

file = open("/triode_rise.wav", "rb")
wave = WaveFile(file)

update_time = time.monotonic()

def play_sound():
    audio.play(wave)
    time.sleep(1)

def find_connection():
    for connection in radio.connections:
        if AppleNotificationService not in connection:
            continue
        if not connection.paired:
            connection.pair()
        return connection, connection[AppleNotificationService]
    return None, None

def check_dim_timeout():
    global update_time
    if a.value or b.value:
        update_time = time.monotonic()
    if time.monotonic() - update_time > DIM_TIMEOUT:
        if display.brightness > DIM_LEVEL:
            display.brightness = DIM_LEVEL
    else:
        if display.brightness == DIM_LEVEL:
            display.brightness = 1.0


# Start advertising before messing with the display so that we can connect immediately.
radio = adafruit_ble.BLERadio()
advertisement = SolicitServicesAdvertisement()
advertisement.complete_name = "CIRCUITPY"
advertisement.solicited_services.append(AppleNotificationService)

def wrap_in_tilegrid(open_file):
    odb = displayio.OnDiskBitmap(open_file)
    return displayio.TileGrid(odb, pixel_shader=displayio.ColorConverter())

display = tft_gizmo.TFT_Gizmo()
group = displayio.Group(max_size=3)
group.append(wrap_in_tilegrid(open("/ancs_connect.bmp", "rb")))
display.show(group)

current_notification = None
current_notifications = {}
all_ids = []
last_press = time.monotonic()
active_connection, notification_service = find_connection()
cleared = False

while True:
    if not active_connection:
        radio.start_advertising(advertisement)

    while not active_connection:
        active_connection, notification_service = find_connection()
        check_dim_timeout()

    # Connected
    update_time = time.monotonic()
    play_sound()

    with open("/ancs_none.bmp", "rb") as no_notifications:
        group.append(wrap_in_tilegrid(no_notifications))
        while active_connection.connected:
            all_ids.clear()
            current_notifications = notification_service.active_notifications
            for id in current_notifications:
                notification = current_notifications[id]
                if notification.app_id not in APP_ICONS or notification.app_id in BLACKLIST:
                    continue
                all_ids.append(id)

            all_ids.sort(key=lambda x: current_notifications[x]._raw_date)

            if current_notification and current_notification.removed:
                # Stop showing the latest and show that there are no new notifications.
                current_notification = None

            if not current_notification and not all_ids and not cleared:
                cleared = True
                update_time = time.monotonic()
                group[1] = wrap_in_tilegrid(no_notifications)
            elif all_ids:
                cleared = False
                now = time.monotonic()
                if current_notification and current_notification.id in all_ids and \
                    now - last_press < DELAY_AFTER_PRESS:
                    index = all_ids.index(current_notification.id)
                else:
                    index = len(all_ids) - 1
                if now - last_press >= DEBOUNCE:
                    if b.value and index > 0:
                        last_press = now
                        index += -1
                    if a.value and index < len(all_ids) - 1:
                        last_press = now
                        index += 1
                id = all_ids[index]
                if not current_notification or current_notification.id != id:
                    update_time = now
                    current_notification = current_notifications[id]
                    print(current_notification._raw_date, current_notification)

                    app_icon_file = open(APP_ICONS[current_notification.app_id], "rb")
                    group[1] = wrap_in_tilegrid(app_icon_file)

            check_dim_timeout()

        group.pop()
        update_time = time.monotonic()
        active_connection = None
        notification_service = None
