
#dht11_sample.py
import RPi.GPIO as GPIO
import dht11
import time
import datetime
 
# initialize GPIO
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
#GPIO.cleanup()
 
# read data using pin 17
instance = dht11.DHT11(pin=14)
 
while True:
    result = instance.read()
    if result.is_valid():
        print("Last valid input: " + str(datetime.datetime.now()))
#        print("Temperature: %d C" % result.temperature)
#        print("Humidity: %d %%" % result.humidity)
 
        print("Temperature: {} C".format(result.temperature))
        print("Humidity: {} %".format(result.humidity))
 
    time.sleep(3)