import logging
import time
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from leropilot.services.hardware.motor_drivers.damiao.drivers import DamiaoCAN_Driver

# Configure logging to see the details
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("DamiaoTest")

def main():
    # Use the interface known from previous conversation
    # User was using PCAN-USB Pro FD
    interface = "pcan:PCAN_USBBUS1" 
    
    print(f"Connecting to {interface}...")
    driver = DamiaoCAN_Driver(interface=interface)
    
    if not driver.connect():
        print("Failed to connect to CAN bus. Make sure PCAN-View is closed and hardware is connected.")
        return

    try:
        print("Connection successful. Starting scan...")
        # Scan range 1-15 (common IDs)
        results = driver.scan_motors(scan_range=list(range(1, 16)))
        
        if not results:
            print("No motors discovered during scan.")
        else:
            print(f"\nScan complete. Found {len(results)} motors:")
            for (send_id, recv_id), info in results.items():
                print(f"  - Motor ID: Send={send_id}, Recv={recv_id} -> Model: {info.model} ({info.description})")
                
    except Exception as e:
        print(f"An error occurred during test: {e}")
        logger.exception(e)
    finally:
        print("Disconnecting...")
        driver.disconnect()

if __name__ == "__main__":
    main()
