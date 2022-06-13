import micropython
import gc
import select
import cellular
import gps
import machine
import socket
import time
import json

class Device:
    def __init__(self, engine_status, preferences, saved_data):
        self.engine_status = engine_status
        self.preferences = preferences
        self.saved_data = saved_data

class Counters:
    def __init__(self, transmitted, connection_error, stored_coordinates):
        self.transmitted = transmitted
        self.connection_error = connection_error
        self.stored_coordinates = stored_coordinates
        self.gprs_error = 0

def blink(led, blink_sleep, range_value):
    value = 1
    range_value = range_value * 2
    for i in range(range_value):
        led.value(value)
        time.sleep(blink_sleep)
        value = 0 if (value == 1) else 1
    return

def read_file(file, ext):
    try:
        with open('t/' + file + '.' + ext, 'r') as file_to_read:
            contents = file_to_read.read()
            return contents

    except Exception as e: error_handler("Error reading " + file + " file:" + str(e))

def error_handler(error):
    try:
        blink(left_led, 0.5, 2)
        print(error)
        with open("t/errors.txt", "a") as error_file:
            error_file.write(error + '\n')
    except Exception: pass

def connect_to_grps(i):
    conn = 0
    while conn < i:
        try:
            print("trying to connect " + str(conn))
            cellular.gprs(entel, "", "")
            print("connected to gprs!")
            counter.gprs_error = 0
            return True
        except Exception:
            counter.gprs_error += 1
            conn += 1
            time.sleep(5)

    if counter.gprs_error > 20:
        machine.reset()
        time.sleep(10)
    return False

def engine_off_function():

    if len(device.saved_data) > 0:
        with open("coordinates", "w") as file:
            file.write(json.dumps(device.saved_data))

    gc.collect()
    machine.watchdog_off()
    gps.off()

    if cellular.is_network_registered():
        cellular.gprs(False)

    machine.idle()
    machine.set_min_freq(32768)

    while True:
        if engine_pin.value() == 1:
            machine.reset()
            time.sleep(10)
            return
        else: time.sleep(30)

def update_script():
    s = socket.socket()
    try:
        response = None
        print("update GPS Function")
        s.connect((device.preferences['domain'], port))
        message = "GET /includes/updateGps.php HTTP/1.1\r\nHost: {}\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n"
        s.write(message.format(device.preferences['domain']))
        ready = select.select([s], [], [], 30)
        if ready[0]:
            response = s.read(32768)
            response = response.decode('utf-8')
        s.close()
        if response != None:
            headers = response.split("\r\n")
            if headers[0] == 'HTTP/1.1 200 OK':
                code = response.split("\r\n\r\n", 1)[-1]
                if "Transfer-Encoding: chunked" in response:
                    code_split = code.split('\r\n', 1)
                    code = code_split[-1]
                    last_line = code.split('\r\n', 1)[-1]
                    second_split = code.rsplit('\r\n')
                    code = second_split[0]
                with open("t/main_ssd.py", "w") as main_file: main_file.write(code)
                with open("t/errors.txt","w") as error_file: error_file.write("Error Log\r\n")
                print("Finished updating script")
                machine.reset()
                time.sleep(10)
    except Exception as update_error: error_handler("Error updating GPS script... " + str(update_error))
    finally: s.close()

def save_coordinates_to_sd():
    try:
        print("Couldn't connect to gprs. Saving data to SD card\r\n")
        blink(left_led, 0.1, 2)

        # WRITE COORDINATES TO FILE
        with open("t/coordinates.txt", "a") as coordinates_file:
            coordinates_file.write(json.dumps(device.saved_data))

    except Exception: pass

def sms_handler(evt):
    print("SMS handler")
    if evt == cellular.SMS_SENT:
        print("SMS sent")
    else:
        try:
            
            print("SMS received, attempting to read ...")
            ls = cellular.SMS.list()
            phone = ls[-1].phone_number
            accepted_phones_list = list(read_file('accepted_phone_numbers', 'txt').split('\r\n'))
            
            if phone in accepted_phones_list:
                # PROCESS SMS AND DO AGPS IF REQUESTED
                message = ls[-1].message
                if message == 'Reboot module!!!':
                    machine.reset()
                    time.sleep(10)

                elif message == 'Get AGPS Data':
                    pass

                elif message == 'Update py script':
                    pass

                elif message == 'posicion actual':
                    pass

                elif message == 'Start transmitting!!!':
                    pass
                else:
                    pass
        except Exception as sms_err:
            error_handler('SMS Handler Error:', str(sms_err))
        finally:
            # REMOVE SMS FROM SIM WHEN DONE
            cellular.SMS.list()[-1].withdraw()
            return

def save_coordinates_to_server():
    s = socket.socket()
    try:

        print("trying to upload to online server\r\n")
        blink(right_led, 0.1, 1)

        response = None
        data = json.dumps({
            "identifier" : "WtQMZj8AxX3P",
            "imei" : imei,
            "coordinates" : device.saved_data
        })

        print("\r\nBody of request:\r\n", data, '\r\n')

        if cellular.gprs() == False and connect_to_grps(3) == False: raise Exception("No GPRS when trying to connect to server")
        s.connect((device.preferences['domain'], port))

        if cellular.gprs() == False: raise Exception("No GPRS")
        s.setblocking(False)

        if cellular.gprs() == False: raise Exception("No GPRS")
        s.send(bytes('POST /includes/gps_post.php HTTP/1.1\r\nHost: {}\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: {}\r\n\r\n{}'.format(device.preferences['domain'], len(data), data), 'utf8'))
        
        if cellular.gprs() == False: raise Exception("No GPRS")
        ready = select.select([s], [], [], 10)
        
        if cellular.gprs() == False: raise Exception("No GPRS")

        if ready[0]:
            if cellular.gprs() == False: raise Exception("No GPRS")
            response = s.recv(384)
            response = response.decode('utf-8')
            print("Response received\r\n", response, "\r\n")
        else: raise Exception("Error getting response from server")
        
        s.close()
        print("\r\nfinished upload\r\n")

        counter.stored_coordinates = 0
        counter.transmitted += 1
        device.saved_data = []

        # PROCESS RESPONSE
        if response != None:
            
            print("processing response")
            response_split = response.split("\r\n")

            if response_split[0] == "HTTP/1.1 200 OK":

                response_body = response.split('\r\n\r\n')[1]

                if "Transfer-Encoding: chunked" in response: body = response_body.split("\r\n")[1]
                else: body = response_body

                json_response = json.loads(body)
                
                if "error" in json_response: raise Exception("Error from server")
                if json_response['success'] == False: raise Exception("Success response from server is false")

                update_preferences = False

                # CHANGE TRIP
                if int(json_response['trip']) != device.preferences['trip']:
                    device.preferences['trip'] = int(json_response['trip'])
                    update_preferences = True

                # CHANGE DOMAIN
                if json_response['domain'] != device.preferences['domain']:
                    device.preferences['domain'] = json_response['domain']
                    update_preferences = True

                # MAX SAVED COORDINATES
                if int(json_response['max_saved_coordinates']) != device.preferences['max_saved_coordinates']:
                    device.preferences['max_saved_coordinates'] = int(json_response['max_saved_coordinates'])
                    update_preferences = True

                # CHANGE STORE COORDINATES
                if int(json_response['store_coordinates']) != device.preferences['store_coordinates']:
                    device.store_coordinates = int(json_response['store_coordinates'])
                    update_preferences = True

                # UPDATE SCRIPT VERSION
                if json_response['script_version'] != device.preferences['script_version']:
                    device.preferences['script_version'] = json_response['script_version']
                    update_preferences = True

                if int(json_response['mcu_sleep']) != device.preferences['mcu_sleep']:
                    device.preferences['mcu_sleep'] = int(json_response['mcu_sleep'])
                    update_preferences = True

                if update_preferences:
                    try:
                        print("changing user preferences")
                        with open("t/preferences.txt", "w") as file:
                            file.write(json.dumps(device.preferences))
                    except Exception as e: error_handler("Error saving user preferences to txt file: " + str(e))

                if int(json_response['reboot']) == 1:
                    machine.reset()
                    time.sleep(10)

    except Exception as e:
        s.close()
        error_handler("Error in save_coordinates_to_server function: " + str(e))
    finally: gc.collect()

def main_loop():
    try:

        machine.watchdog_reset()
        satellites = gps.get_satellites()
        tracked_satellites = satellites[0]

        #CONNECTED TO ENOUGH SATELLITES
        if tracked_satellites >= 3:
            
            print("Connected to", tracked_satellites, "\r\n")
            location = gps.get_location()
            nmea = gps.nmea_data()
            vtg = nmea[6]

            data = {
                "last_location" : False,
                "counter" : counter.transmitted,
                "timestamp" : gps.time(),
                "trip" : device.preferences['trip'],
                "latitude" : location[0],
                "longitude" : location[1],
                "speed" : vtg[3],
                "gprs" : cellular.get_signal_quality()[0],
                "satellites" : tracked_satellites,
                "engine_status" : device.engine_status
            }

            #REMOVE FIRST OBJECT FROM ARRAY TO MAKE ROOM FOR THE LATEST DATA
            if counter.stored_coordinates > device.preferences['max_saved_coordinates'] and len(counter.stored_coordinates) > 0: device.saved_data.pop(0)
            device.saved_data.append(data)
            counter.stored_coordinates += 1

            #UPLOAD TO SERVER
            if device.preferences['store_coordinates'] == 0 or len(device.saved_data) > device.preferences['max_saved_coordinates']:

                if cellular.is_network_registered():

                    # NO GRPS AFTER 3 RECONNECTION ATTEMPTS RAISES AN ERROR
                    if cellular.gprs() == False and connect_to_grps(3) == False: raise Exception("No GPRS connection available")

                    # TRY AND SAVE TO ONLINE DB
                    save_coordinates_to_server()
                        
                else: print("not registered in network")    

            print("Amount of coordinates saved:", counter.stored_coordinates, "\r\n")

        #NOT ENOUGH SATELLITES AVAILABLE
        else:
            
            print("Not enough satellites to triangulate position. Connected to", tracked_satellites, "\r\n")

            if device.engine_status == 'off':

                location = gps.get_last_location()
                data = {
                    "last_location" : True,
                    "counter" : counter.transmitted,
                    "trip" : device.preferences['trip'],
                    "latitude" : location[0],
                    "longitude" : location[1],
                    "engine_status" : device.engine_status
                }

                device.saved_data.append(data)

                if cellular.is_network_registered():
                    #SAVE TO SD IF NO GPRS
                    if cellular.gprs() == False and connect_to_grps(3) == False: save_coordinates_to_sd()
                    else: save_coordinates_to_server()
                
                #save to sd if not connected to network
                else: save_coordinates_to_sd()

                engine_off_function()
            else:
                blink(right_led, 0.1, 3)
                print("Less than minimum amount of satellites connected to triangulate position...Sleeping 5 seconds...\r\n")
                time.sleep(5)

        #ENGINE IS ON
        if engine_pin.value() == 1:
            print("engine is on\r\n")

            if device.engine_status == 'off': device.engine_status = 'on'
            machine.watchdog_reset()

            if cellular.is_network_registered() and cellular.gprs():
                print("Sleeping for", device.preferences['mcu_sleep'], "seconds\r\n")
                time.sleep(device.preferences['mcu_sleep'])
            else:
                print("Sleeping for 50 seconds\r\n")
                time.sleep(50)

            print("--- BREAK ---\r\n\r\n")

        #ENGINE IS OFF
        else:
            if device.engine_status == 'on': device.engine_status = 'off'
            else: engine_off_function()

    except Exception as loop_error: error_handler("Error in main_loop: " + str(loop_error))
    finally: gc.collect()

print("Loading main variables...\r\n")

cellular.on_sms(sms_handler)

imei = cellular.get_imei()
# entel = "m2m.entel.cl"
entel = "bam.entelpcs.cl"
port = 80

right_led = machine.Pin(27, machine.Pin.OUT, 0)
left_led = machine.Pin(28, machine.Pin.OUT, 0)
engine_pin = machine.Pin(29, machine.Pin.IN)

if engine_pin.value() == 1: engine = 'on'
else: engine = 'off'

preferences = None

try:
    with open("t/coordinates.txt", "r") as file:
        read_coordinates = file.read()
        if len(read_coordinates) > 0: saved_coordinates = json.loads(file.read())
        else: saved_coordinates = []
    try:
        with open("t/preferences", "r") as file: preferences = json.loads(file.read())
    except Exception as e: preferences = { 'trip': 0, 'domain': 'gpspost.mslepe.cl', 'max_saved_coordinates': 3, 'store_coordinates': 0, 'script_version': '0.2', 'mcu_sleep': 5 }
except Exception as open_coordinates_err: saved_coordinates = []

finally:
    device = Device(engine, preferences, saved_coordinates)
    device.preferences['trip'] = device.preferences['trip'] + 1
    counter = Counters(0, 0, len(saved_coordinates))
    machine.watchdog_on(70)

    print("All variables loaded and watchdog ON... Starting main try and loop...\r\n")
    print(device.preferences, '\r\n')
    
    if device.engine_status == 'on':
        gps.on()
        connect_to_grps(5)
        while True: main_loop()
    else: engine_off_function()
