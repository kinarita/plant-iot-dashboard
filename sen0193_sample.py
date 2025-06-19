# sen0193_sample.py
import time
import datetime
import sen0193

# Initialize sensor
sensor = sen0193.SEN0193(channel=0, vref=5.0)

print("SEN0193 Capacitive Soil Moisture Sensor Sample")
print("Press Ctrl+C to stop")

while True:
    try:
        if sensor.is_valid():
            print("Last valid input: " + str(datetime.datetime.now()))
            
            raw_voltage = sensor.read_raw_voltage()
            moisture_percent = sensor.read_moisture_percentage()
            
            print("Voltage: {:.3f} V".format(raw_voltage))
            print("Moisture: {} %".format(moisture_percent))
            print("-" * 30)
        else:
            print("Invalid sensor reading")
            
        time.sleep(3)
        
    except KeyboardInterrupt:
        print("\nProgram stopped by user")
        break
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(1)