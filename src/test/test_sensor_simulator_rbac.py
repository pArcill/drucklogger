"""
Test module for verifying RBAC implementation for SensorSimulator objects

This test suite validates that:
1. SensorSimulator objects properly store clearance levels
2. Clearance levels are included in MQTT messages
3. MQTTHandler correctly extracts and applies clearance levels to sensors in the database
"""

import json
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime

# Import the classes to test
import sys
import os

# Add parent directories to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sensor_simulator.main import SensorSimulator, SensorStatus, MeasurementData
from fastapi_backend.mqtt_handler import MQTTHandler
from fastapi_backend.models import Sensor, Measurement
from fastapi_backend.role_config import can_access_readings, can_view_sensor


class TestSensorSimulatorRBAC(unittest.TestCase):
    """Test RBAC functionality in SensorSimulator"""
    
    def test_sensor_simulator_stores_clearance_levels(self):
        """Verify SensorSimulator properly stores display_clearance and readings_clearance"""
        # Create a sensor with default clearance
        with patch.object(SensorSimulator, '_connect_with_retry'):
            sensor_default = SensorSimulator("AA:BB:CC:00:11:22", "localhost", 1883)
            self.assertEqual(sensor_default.display_clearance, "regular")
            self.assertEqual(sensor_default.readings_clearance, "regular")
            sensor_default.client.loop_stop()
            sensor_default.client.disconnect()
            
            # Create a sensor with elevated clearance
            sensor_elevated = SensorSimulator(
                "AA:BB:CC:00:11:23", 
                "localhost", 
                1883,
                display_clearance="elevated",
                readings_clearance="full_clearance"
            )
            self.assertEqual(sensor_elevated.display_clearance, "elevated")
            self.assertEqual(sensor_elevated.readings_clearance, "full_clearance")
            sensor_elevated.client.loop_stop()
            sensor_elevated.client.disconnect()


class TestSensorStatusWithClearance(unittest.TestCase):
    """Test that SensorStatus includes clearance information"""
    
    def test_sensor_status_includes_clearance(self):
        """Verify SensorStatus dataclass includes display_clearance and readings_clearance"""
        status = SensorStatus(
            mac="AA:BB:CC:00:11:22",
            battery=0.85,
            latitude=47.8095,
            longitude=13.0550,
            altitude=400.0,
            display_clearance="elevated",
            readings_clearance="top_secret",
            timestamp=datetime.now().isoformat()
        )
        
        # Verify fields are accessible
        self.assertEqual(status.display_clearance, "elevated")
        self.assertEqual(status.readings_clearance, "top_secret")
        
        # Verify that asdict includes the clearance fields
        from dataclasses import asdict
        status_dict = asdict(status)
        self.assertIn("display_clearance", status_dict)
        self.assertIn("readings_clearance", status_dict)
        self.assertEqual(status_dict["display_clearance"], "elevated")
        self.assertEqual(status_dict["readings_clearance"], "top_secret")


class TestMeasurementDataWithClearance(unittest.TestCase):
    """Test that MeasurementData includes clearance information"""
    
    def test_measurement_data_includes_clearance(self):
        """Verify MeasurementData dataclass includes display_clearance and readings_clearance"""
        measurement = MeasurementData(
            mac="AA:BB:CC:00:11:22",
            pressure=1013.25,
            display_clearance="full_clearance",
            readings_clearance="full_clearance",
            timestamp=datetime.now().isoformat()
        )
        
        # Verify fields are accessible
        self.assertEqual(measurement.display_clearance, "full_clearance")
        self.assertEqual(measurement.readings_clearance, "full_clearance")
        
        # Verify that asdict includes the clearance fields
        from dataclasses import asdict
        measurement_dict = asdict(measurement)
        self.assertIn("display_clearance", measurement_dict)
        self.assertIn("readings_clearance", measurement_dict)
        self.assertEqual(measurement_dict["display_clearance"], "full_clearance")
        self.assertEqual(measurement_dict["readings_clearance"], "full_clearance")


class TestMQTTHandlerClearanceExtraction(unittest.TestCase):
    """Test that MQTTHandler correctly extracts and uses clearance information"""
    
    def test_mqtt_handler_extracts_clearance_from_status(self):
        """Verify MQTTHandler extracts clearance from sensor status messages"""
        # Create mock MQTT handler
        handler = MQTTHandler("localhost", 1883)
        
        # Mock the session and database operations
        with patch('fastapi_backend.mqtt_handler.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value.__enter__.return_value = mock_session
            
            # Create a mock sensor that doesn't exist yet
            mock_session.exec.return_value.first.return_value = None
            
            # Prepare test data with clearance levels
            status_data = {
                "mac": "AA:BB:CC:00:11:22",
                "battery": 0.85,
                "latitude": 47.8095,
                "longitude": 13.0550,
                "altitude": 400.0,
                "display_clearance": "elevated",
                "readings_clearance": "full_clearance",
                "timestamp": datetime.now().isoformat()
            }
            
            # Call the handler
            handler._handle_sensor_status(status_data)
            
            # Verify that a Sensor was created with the correct clearance levels
            # We need to check what was passed to session.add()
            mock_session.add.assert_called()
            created_sensor = mock_session.add.call_args[0][0]
            
            self.assertIsInstance(created_sensor, Sensor)
            self.assertEqual(created_sensor.display_clearance, "elevated")
            self.assertEqual(created_sensor.readings_clearance, "full_clearance")
            self.assertEqual(created_sensor.mac_address, "AA:BB:CC:00:11:22")
    
    def test_mqtt_handler_extracts_clearance_from_measurement(self):
        """Verify MQTTHandler extracts clearance from measurement data messages"""
        handler = MQTTHandler("localhost", 1883)
        
        with patch('fastapi_backend.mqtt_handler.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value.__enter__.return_value = mock_session
            
            # Create a mock sensor that doesn't exist yet
            mock_session.exec.return_value.first.return_value = None
            
            # Prepare test data with clearance levels
            measurement_data = {
                "mac": "AA:BB:CC:00:11:22",
                "pressure": 1013.25,
                "display_clearance": "full_clearance",
                "readings_clearance": "top_secret",
                "out_of_range": False,
                "timestamp": datetime.now().isoformat()
            }
            
            # Call the handler
            handler._handle_measurement_data(measurement_data)
            
            # Verify that a Sensor was created with the correct clearance levels
            mock_session.add.assert_called()
            
            # Find the Sensor object in the add calls (not Measurement)
            sensor_created = False
            for call in mock_session.add.call_args_list:
                obj = call[0][0]
                if isinstance(obj, Sensor):
                    sensor_created = True
                    self.assertEqual(obj.display_clearance, "full_clearance")
                    self.assertEqual(obj.readings_clearance, "top_secret")
                    self.assertEqual(obj.mac_address, "AA:BB:CC:00:11:22")
                    break
            
            self.assertTrue(sensor_created, "Sensor object was not created")


class TestRoleBasedAccessControl(unittest.TestCase):
    """Test that RBAC functions work correctly with sensors from SensorSimulator"""
    
    def test_can_view_sensor_with_different_clearances(self):
        """Verify role-based access control for viewing sensors"""
        # Test with regular user
        self.assertTrue(can_view_sensor("regular", "regular"))
        self.assertFalse(can_view_sensor("regular", "elevated"))
        
        # Test with elevated user
        self.assertTrue(can_view_sensor("elevated", "regular"))
        self.assertTrue(can_view_sensor("elevated", "elevated"))
        self.assertFalse(can_view_sensor("elevated", "full_clearance"))
        
        # Test with full clearance user
        self.assertTrue(can_view_sensor("full_clearance", "regular"))
        self.assertTrue(can_view_sensor("full_clearance", "elevated"))
        self.assertTrue(can_view_sensor("full_clearance", "full_clearance"))
    
    def test_can_access_readings_with_different_clearances(self):
        """Verify role-based access control for readings"""
        # Test with regular user
        self.assertTrue(can_access_readings("regular", "regular"))
        self.assertFalse(can_access_readings("regular", "elevated"))
        
        # Test with elevated user
        self.assertTrue(can_access_readings("elevated", "regular"))
        self.assertTrue(can_access_readings("elevated", "elevated"))
        self.assertFalse(can_access_readings("elevated", "full_clearance"))
        
        # Test with guest user
        self.assertFalse(can_access_readings("guest", "regular"))
        self.assertFalse(can_access_readings("guest", "elevated"))


if __name__ == "__main__":
    unittest.main()
