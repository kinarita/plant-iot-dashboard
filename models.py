from sqlalchemy import Column, Integer, Float, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class SensorData(Base):
    __tablename__ = 'sensor_data'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.now)
    temperature = Column(Float)
    humidity = Column(Float)
    soil_moisture = Column(Float)
