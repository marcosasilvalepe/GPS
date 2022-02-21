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
    def __init__(self, engine_status, script_version, trip, sleep_value, stored_coordinates, force_transmit):
        self.engine_status = engine_status
        self.script_version = script_version
        self.trip = trip
        self.sleep_value = sleep_value
        self.force_transmit = force_transmit
class Counters:
    def __init__(self, transmitted, connection_error, stored_coordinates):
        self.transmitted = transmitted
        self.connection_error = connection_error
        self.stored_coordinates = stored_coordinates

def blink(led, blink_sleep, range_value):
    value = 1
    range_value = range_value * 2
    for i in range(range_value):
        led.value(value)
        time.sleep(blink_sleep)
        value = 0 if (value==1) else 1
    return
def read_file(file, ext):
    try:
        file = open('t/' + file + '.' + ext, 'r')
        contents = file.read()
        file.close
        return contents
    except Exception as e:
        errorHandler("Error reading " + file + " file:" + str(e))
def errorHandler(error):
    try:
        print(error)
        blink(left_led, 0.5, 2)
        save_error = open("t/errors.txt","a")
        save_error.write(error + '\r\n')
        save_error.close()
    except Exception:
        pass
    finally:
        return
def gprsConnect(i):
    conn = 0
    while conn < i:
        try:
            cellular.gprs(entel, "", "")
            return True
        except Exception:
            conn += 1
            time.sleep(5)
    return False
def engine_off_function():
    machine.watchdog_off()
    if cellular.is_network_registered():
        cellular.gprs(False)
    gps.off()
    machine.set_min_freq(32768)
    while True:
        if engine_pin.value()==1:
            machine.reset()
            time.sleep(10)
            return
        else:
            time.sleep(30)
def updateGpsVersion():
    try:
        print("update GPS Function")
        s = socket.socket()
        s.connect((url, port))
        message = "GET /includes/updateGps.php HTTP/1.1\r\nHost: {}\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n"
        s.write(message.format(url))
        ready = select.select([s], [], [], 30)
        if ready[0]:
            response = s.read(32768)
            response = response.decode('utf-8')
            s.close()
            ls = response.split("\r\n")
            if ls[0] == 'HTTP/1.1 200 OK':
                code = response.split("\r\n\r\n", 1)[-1]
                if ls[3]=='Transfer-Encoding: chunked':
                    code_split = code.split('\r\n', 1)
                    code = code_split[-1]
                    last_line = code.split('\r\n', 1)[-1]
                    second_split = code.rsplit('\r\n')
                    code = second_split[0]
                main = open("t/main_ssd.py","w")
                main.write(code)
                main.close()
                error_log = open("t/errors.txt","w")
                error_log.write("ERROR LOG\r\n")
                error_log.close()
                print("Finished... Resetting...")
                machine.reset()
                time.sleep(10)
    except Exception as update_error:
        errorHandler("Error updating GPS script... " + str(update_error))
    finally:
        return
def post_error():
    try:
        contents = read_file('errors', 'txt')
        error_array = contents.split('\r\n')
        error_array.insert(0, imei)
        error_array.append("SCbi4yaHBO")
        json_error = json.dumps(error_array)
        if cellular.is_network_registered():
            if cellular.gprs()==False:
                gprsConnect(5)
            rsp = None
            s = socket.socket()
            s.connect((url, port))
            s.send(bytes('POST /includes/pythonGps.php HTTP/1.1\r\nHost: {}\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: {}\r\n\r\n{}'.format(url, len(json_error), json_error), 'utf8'))
            ready = select.select([s], [], [], 10)
            if ready[0]:
                response=s.recv(256)
                rsp = response.decode('utf-8')
            s.close()
            if rsp != None:
                if rsp.split('\r\n', 1)[0]=="HTTP/1.1 200 OK":
                    body = rsp.split('\r\n\r\n')[-1]
                    if body=="OK":
                        open('t/errors.txt', 'w').close()
    except Exception as e:
        print(str(e))
        errorHandler("Error in post_error function: " + str(e))
    finally:
        return
def saveCoordinates(body):
    try:
        print("Couldn't connect to gprs. Saving data to SD card\r\n")
        blink(left_led, 0.1, 2)
        # WRITE COORDINATES TO FILE
        if counter.stored_coordinates < 200:
            f = open("t/coordinates.txt","w")
            f.write(body)
            f.close()
            counter.stored_coordinates += 1
        counter.connection_error += 1
        if counter.connection_error > 50:
            print("Too many errors while trying to connect to the internet... Gonna reboot to see if that solves the problem\r\n")
            machine.reset()
            time.sleep(10)
    except Exception:
        pass
    finally:
        return

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
                if message=='Reboot module!!!':
                    machine.reset()
                    time.sleep(10)
                elif message=='Get AGPS Data':
                    agps_location = agps.get_location_opencellid(cellular.agps_station_data(), "pk.8b8e5bce0149cbf00665518cf19bebcb")
                    agps_lat = agps_location[1]
                    agps_lng = agps_location[0]
                    cellular.SMS(phone, agps_location).send()
                elif message=='Update py script':
                    machine.set_min_freq(156000000)
                    if cellular.flight_mode():
                        cellular.flight_mode(False)
                elif message=='Connect and transmit once':
                    machine.set_min_freq(156000000) #should be normal frequency here!!!
                    gps_err_counter = 0
                    gps.on()
                    satellites = gps.get_satellites()
                    tracked_satellites = satellites[0]

                    while tracked_satellites < 4:
                        if gps_err_counter > 10:
                            return
                        gps_err_counter += 1
                        time.sleep(20)
                    gprs_err_counter = 0

                    if gprsConnect(10):
                        now = gps.time()
                        loc = gps.get_location()
                        lat = loc[0]
                        lng = loc[1]
                        nmea = gps.nmea_data()
                        vtg = nmea[6]
                        speed = vtg[3]
                        signal_strength = cellular.get_signal_quality()
                        if enginePin.value()==1:
                            car_status = "on"
                        else:
                            car_status = "off"
                        data_array = '{"ts": "' + str(now) + '", "trip": "' + str(trip) +  '", "lat": "' + str(lat) + '", "lng": "' + str(lng) + '", "speed": "' + str(speed) + '", "sats": "' + str(tracked_satellites) + '", "2g": "' + str(signal_strength[0]) + '", "cstat": "' + car_status + '"}'
                        body = '{"?QSN2v3R+#": "1", "v": "' + version + '", "imei": "' + str(imei) + '", "counter": "' + str(counter) + '", "data": ' + '[' + data_array + ']}'
                        postData(body)
                        cellular.gprs(False)
                        gps.off()
                        machine.set_min_freq(32768)
                    else:
                        #SEND MESSAGE THAT I COULDNT GET CONNECTED TO GPRS
                        return
                elif message=='Start transmitting!!!':
                    gps.on()
                    try:
                        cellular.gprs(entel, "", "")
                    except Exception:
                        pass
                    finally:
                        device.force_transmit = True
                        while True:
                            gpsLoopFunction()
                else:
                    pass
        except Exception as sms_err:
            errorHandler('SMS Handler Error:', str(sms_err))
        finally:
            # REMOVE SMS FROM SIM WHEN DONE
            cellular.SMS.list()[-1].withdraw()
            return

def postData(body):
    try:
        blink(right_led, 0.1, 1)
        rsp = None
        s = socket.socket()
        print("Body of request:\r\n", body, '\r\n')
        s.connect((url, port))
        s.setblocking(False)
        s.send(bytes('POST /includes/pythonGps.php HTTP/1.1\r\nHost: {}\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: {}\r\n\r\n{}'.format(url, len(body), body), 'utf8'))
        ready = select.select([s], [], [], 10)
        if ready[0]:
            response=s.recv(256)
            rsp = response.decode('utf-8')
            print("Response received\r\n", rsp, "\r\n")
        s.close()
        # PROCESS RESPONSE
        if rsp != None:
            response_body = rsp.split("\r\n")
            if response_body[0]=="HTTP/1.1 200 OK":
                # DELETE DATA FROM COORDINATES.TXT
                if counter.stored_coordinates > 0:
                    open("t/coordinates.txt", "w").close()
                    counter.stored_coordinates=0
                response_vars = rsp.split('\r\n\r\n')[-1]
                vars_split = response_vars.split(":")
                print(response_vars)
                if device.script_version != vars_split[0]:
                    updateGpsVersion()
                if device.sleep_value != int(vars_split[1]):
                    device.sleep_value = int(vars_split[1])
                if device.trip != int(vars_split[2]):
                    device.trip = int(vars_split[2])
                if int(vars_split[3])==1:
                    post_error()
    except Exception as e:
        errorHandler("Error in PostData function: " + str(e))
    finally:
        return

def gpsLoopFunction():
    try:
        machine.watchdog_reset()
        satellites = gps.get_satellites()
        tracked_satellites = satellites[0]
        visible_satellites = satellites[1]
        if tracked_satellites < 3:
            if device.engine_status=='off':
                loc = gps.get_last_location()
                lat = loc[0]
                lng = loc[1]
                signal_strength = cellular.get_signal_quality()
                data_array = '{"counter": "' + str(counter.transmitted) + '", "ts": "0", "trip": "' + str(device.trip) +  '", "lat": "' + str(lat) + '", "lng": "' + str(lng) + '", "speed": "0", "sats": "0", "2g": "' + str(signal_strength[0]) + '", "cstat": "off"}'
                if counter.stored_coordinates > 0:
                    saved_coordinates = read_file('coordinates', 'txt')
                    saved_coordinates = saved_coordinates[:-2]
                    body = saved_coordinates + ',' + data_array + ']}'
                else:
                    body = '{"?QSN2v3R+#": "1", "v": "' + device.script_version + '", "imei": "' + str(imei) + '", "data": ' + '[' + data_array + ']}'
                if cellular.gprs():
                    postData(body)
                else:
                    if gprsConnect(5):
                        postData(body)
                    else:
                        saveCoordinates(body)
                engine_off_function()
            else:
                blink(right_led, 0.1, 3)
                print("Less than minimum amount of satellites connected to triangulate position...Sleeping 5 seconds...\r\n")
                time.sleep(device.sleep_value)
        else:
            now = gps.time()
            loc = gps.get_location()
            lat = loc[0]
            lng = loc[1]
            nmea = gps.nmea_data()
            vtg = nmea[6]
            speed = vtg[3]
            signal_strength = cellular.get_signal_quality()
            data_array = '{"counter": "' + str(counter.transmitted) + '", "ts": "' + str(now) + '", "trip": "' + str(device.trip) +  '", "lat": "' + str(lat) + '", "lng": "' + str(lng) + '", "speed": "' + str(speed) + '", "sats": "' + str(tracked_satellites) + '", "2g": "' + str(signal_strength[0]) + '", "cstat": "' + device.engine_status + '"}'
            if counter.stored_coordinates > 0:
                saved_coordinates = read_file('coordinates', 'txt')
                saved_coordinates = saved_coordinates[:-2]
                body = saved_coordinates + ',' + data_array + ']}'
            else:
                body = '{"?QSN2v3R+#": "1", "v": "' + device.script_version + '", "imei": "' + str(imei) + '", "data": ' + '[' + data_array + ']}'
            if cellular.is_network_registered():
                if cellular.gprs():
                    postData(body)
                else:
                    print("Im NOT connected. Gonna try and connect now ...")
                    try:
                        cellular.gprs(entel, "", "")
                        postData(body)
                    except Exception:
                        saveCoordinates(body)
            else:
                saveCoordinates(body)
            print("Amount of coordinates saved in SD Card:", counter.stored_coordinates, "\r\n")
            counter.transmitted += 1
            gc.collect()
        if engine_pin.value()==1: #Engine is ON
            if device.engine_status=='off':
                device.engine_status='on'
            if counter.stored_coordinates < 10:
                print("Sleeping for:", device.sleep_value, "seconds\r\n")
                time.sleep(device.sleep_value)
            else:
                print("Sleeping for 50 seconds\r\n")
                machine.watchdog_reset()
                time.sleep(50)
            print("----------------- BREAK -----------------\r\n\r\n")
        else: #EL MOTOR ESTA APAGADO!!!!
            if device.force_transmit==False and device.engine_status=='off':
                engine_off_function()
            elif device.force_transmit==False and device.engine_status=='on':
                device.engine_status='off'
                time.sleep(7)
                return
            elif device.force_transmit and device.engine_status=='off':
                device.engine_status='on'
                return
            else:
                pass              
    except Exception as loop_error:
        errorHandler("Error in gpsLoopFunction: " + str(loop_error))
    finally:
        return

print("Loading main variables...\r\n")
cellular.on_sms(sms_handler)
imei = cellular.get_imei()
entel = "m2m.entel.cl"
url = "gpspost.mslepe.cl"
port = 80
right_led = machine.Pin(27, machine.Pin.OUT, 0)
left_led = machine.Pin(28, machine.Pin.OUT, 0)
engine_pin = machine.Pin(29, machine.Pin.IN)

if engine_pin.value()==1:
    engine = 'on'
else:
    engine = 'off'

try:
    coordinates_contents = read_file('coordinates', 'txt')
    if len(coordinates_contents)==0:
        saved_coordinates = False
        saved_coordinates_counter = 0
    else:
        saved_coordinates = True
        coordinates_json = json.loads(coordinates_contents)
        saved_coordinates_counter = len(coordinates_json["data"])
except Exception as open_coordinates_err:
    saved_coordinates = False
    saved_coordinates_counter = 0
finally:
    device = Device(engine, '0.2', 0, 7, saved_coordinates, False)
    counter = Counters(0, 0, saved_coordinates_counter)
    machine.watchdog_on(60)
    print("All variables loaded and watchdog ON... Starting main try and loop...\r\n")
    
    if device.engine_status=='on':
        gps.on()
        gprsConnect(2)
        while True:
            gpsLoopFunction()
    else:
        engine_off_function()