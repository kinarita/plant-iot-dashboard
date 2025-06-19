#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SEN0193 Capacitive Soil Moisture Sensor Class
Raspberry Pi + MCP3002 A/D Converter
"""

from gpiozero import MCP3002

class SEN0193:
    """SEN0193 Capacitive Soil Moisture Sensor Reader Class"""
    
    def __init__(self, channel=0, vref=5.0):
        """
        Initialize SEN0193 sensor
        Args:
            channel: MCP3002 channel (0 or 1)
            vref: Reference voltage (should match MCP3002 Vdd/Vref)
        """
        self.adc = MCP3002(channel=channel)
        self.vref = vref
        
        # Calibration values (実際の環境に応じて調整が必要)
        # これらの値は、センサーを完全に乾燥した土壌と湿潤な土壌に配置して校正する必要があります
        self.dry_value = 2.8  # 完全乾燥時の電圧値（空気中での値に基づき調整）
        self.wet_value = 1.5  # 完全湿潤時の電圧値
    
    def read_raw_voltage(self):
        """Read raw voltage from sensor"""
        return self.adc.value * self.vref
    
    def read_moisture_percentage(self):
        """
        Convert voltage to moisture percentage
        Returns: Moisture percentage (0-100%)
        """
        voltage = self.read_raw_voltage()
        
        # Convert voltage to percentage (inverse relationship)
        # Higher voltage = drier soil = lower moisture percentage
        if voltage >= self.dry_value:
            return 0.0  # Completely dry
        elif voltage <= self.wet_value:
            return 100.0  # Completely wet
        else:
            # Linear interpolation
            moisture = 100.0 * (self.dry_value - voltage) / (self.dry_value - self.wet_value)
            return round(moisture, 1)
    
    def calibrate_dry(self):
        """Calibrate dry value (call when sensor is in dry soil)"""
        voltage = self.read_raw_voltage()
        self.dry_value = voltage
        print(f"Dry calibration set to: {voltage:.3f}V")
    
    def calibrate_wet(self):
        """Calibrate wet value (call when sensor is in wet soil)"""
        voltage = self.read_raw_voltage()
        self.wet_value = voltage
        print(f"Wet calibration set to: {voltage:.3f}V")
    
    def is_valid(self):
        """Check if sensor reading is valid (compatibility with DHT11 style)"""
        try:
            voltage = self.read_raw_voltage()
            # Check if voltage is within expected range for SEN0193
            return 0.5 <= voltage <= 3.5
        except:
            return False