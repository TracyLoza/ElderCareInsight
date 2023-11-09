#!/usr/bin/env python
from sqlalchemy import *
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base, DeclarativeMeta
import os.path
from digi.xbee.devices import XBeeDevice
from digi.xbee.models.options import DiscoveryOptions
import subprocess as sp
import time
import paho.mqtt.client as mqtt
from threading import Thread
import json

gateway_id = "main-gateway" # EDIT THIS WHEN INSTALLING A NEW GATEWAY DEVICE

# database initialization
engine = create_engine('sqlite:///gateway.db', echo = False)
Base = declarative_base()

# Device table definition
class Device(Base):
    __tablename__ = 'devices'

    id = Column(Integer, primary_key = True)
    system_id = Column(String)
    name = Column(String) 
    xbee_id = Column(String)
    memory_space = Column(Integer)
    battery_capacity = Column(Integer)
    installed = Column(Integer)
    group = Column(String) 
    status = Column(String)

# Json serializer for MQTT sync with the cloud
class AlchemyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj.__class__, DeclarativeMeta):
            # an SQLAlchemy class
            fields = {}
            for field in [x for x in dir(obj) if not x.startswith('_') and x != 'metadata']:
                data = obj.__getattribute__(field)
                try:
                    json.dumps(data) # this will fail on non-encodable values, like other classes
                    fields[field] = data
                except TypeError:
                    fields[field] = None
            # a json-encodable dict
            return fields

        return json.JSONEncoder.default(self, obj)

# MQTT
def when_connected_to_mqtt(client, userdata, flags, rc):
    print("Connected successfully to Broker")
    client.publish("/hospital/gateway",gateway_id+" connected")

    # subscribe to post processing topics
    client.subscribe("/hospital/gateway/new-response")
    
# This function is mainly in charge of processing incoming messages from the cloud
def when_new_message(client, userdata, message):
    # process response messages after registering, updating, deactivating devices
    if(message.topic == "/hospital/gateway/new-response"):
        print(message.payload.decode("utf-8"))

client = mqtt.Client()
client.on_connect = when_connected_to_mqtt
client.on_message = when_new_message

client.connect("127.0.0.1",1883,60)
client.loop()
# END MQTT

Base.metadata.create_all(engine)

# create a configured "Session" class
Session = sessionmaker(bind=engine)
# create a Session
session = Session()

def check_devices():
    # get the list of saved devices
    result = session.query(Device).all()

    saved_devices = []

    # check if there was at least one saved device
    for row in result: 
        saved_devices.append((row.id, row.system_id, row.name, row.xbee_id, 
        row.memory_space, row.battery_capacity, row.installed, row.group, row.status))

    # set up local device USB port 
    xbee = XBeeDevice("/dev/cu.usbserial-A50285BI", 9600) # EDIT THIS WHEN INSTALLING A NEW GATEWAY DEVICE


    # open connection with local Xbee 
    xbee.open()
    
    # get the XbeeNetwork object
    xnet = xbee.get_network()

    # configure the discovery options
    xnet.set_discovery_options({DiscoveryOptions.APPEND_DD})
    xnet.set_discovery_timeout(5)

    # start the discovery
    xnet.start_discovery_process()
    while xnet.is_discovery_running():
        # wait until the process finished
        time.sleep(0.0001)
    
    if saved_devices: 
        print("Some existent devices. Checking if they are connected.")
        all_devices = xnet.get_devices()

        # check if there are missing devices
        for saved in saved_devices:
            present = False
            for current_device in all_devices: 
                name = str(current_device)
                xbee_id=name.split(" ")[0] 
                if xbee_id == saved[3]:
                    present = True

            
            if not present: 
                missing_device = session.query(Device).filter(Device.xbee_id == saved[3]).first()
                if missing_device:
                    missing_device.status = "disconnected"
                    session.commit()
                    print("Device", saved[3],"disconnected")

                    # Publish via MQTT
                    client.publish("/hospital/gateway/"+saved[3],"disconnected")
            else:
                print("Device", saved[3], "active")
        
        # check new devices
        for current_device in all_devices:
            present = False
            for saved in saved_devices:
                name = str(current_device)
                xbee_id=name.split(" ")[0] 
                if xbee_id in saved:
                    present = True
                    
            if present:
                if saved[8] == "disconnected":
                    missing_device = session.query(Device).filter(Device.xbee_id == saved[3]).first()
                    if missing_device: 
                        missing_device.status = "connected"
                        session.commit()

                        # Publish via MQTT
                        client.publish("/hospital/gateway/"+saved[3],"connected")

            else: 
                print ("New device detected")
                name = str(current_device)
                xbee_id=name.split(" ")[0] 
                new_device = Device(
                    system_id="",
                    name=name,
                    xbee_id=xbee_id,
                    memory_space=500,
                    battery_capacity=500,
                    installed=0,
                    group="",
                    status="connected", 
                )
                session.add(new_device)
                session.commit()

                # Json serialization of the IoT device's details
                message = json.dumps(new_device, cls=AlchemyEncoder)
                # Publish via MQTT
                client.publish("/hospital/gateway/new",
                json.dumps(new_device, cls=AlchemyEncoder)
                )

    else: 
        print("Local database with no entries")

        new_devices = xnet.get_devices()

        if new_devices:
            for new in new_devices:
                print ("New device detected")
                name = str(new)
                xbee_id=name.split(" ")[0] 
                new_device = Device(
                    system_id="",
                    name=name,
                    xbee_id=xbee_id,
                    memory_space=500,
                    battery_capacity=500,
                    installed=0,
                    group="",
                    status="connected", 
                )
                session.add(new_device)
                session.commit()

                # Json serialization of the IoT device's details
                message = json.dumps(new_device, cls=AlchemyEncoder)
                # Publish via MQTT
                client.publish("/hospital/gateway/new",
                json.dumps(new_device, cls=AlchemyEncoder)
                )

        else:
            print("No new devices")
    
    xbee.close()

def start_gateway():
    # launch cron or celery tasks here
    while True:
        check_devices()
        time.sleep(10)

if __name__ == "__main__":
    start_gateway()
   