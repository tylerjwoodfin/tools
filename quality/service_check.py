#!/usr/bin/env python3
import subprocess
import os
from datetime import datetime
import time
from cabinet import Cabinet

def run_command(command):
    """Run a shell command and return the result"""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return False, "", str(e)

def check_docker_container(container_name):
    """Check if a Docker container is running"""
    success, output, error = run_command(f"docker ps --filter name={container_name} --format '{{{{.Names}}}}'")
    if success and container_name in output:
        return True
    return False

def check_system_service(service_name):
    """Check if a system service is running"""
    success, output, error = run_command(f"systemctl is-active {service_name}")
    return success and output.strip() == "active"

def get_disk_usage(path):
    """Get disk usage information for a path"""
    try:
        statvfs = os.statvfs(path)
        total_bytes = statvfs.f_frsize * statvfs.f_blocks
        free_bytes = statvfs.f_frsize * statvfs.f_bavail
        used_bytes = total_bytes - free_bytes
        
        total_gb = total_bytes / (1024**3)
        free_gb = free_bytes / (1024**3)
        used_gb = used_bytes / (1024**3)
        
        return {
            'total_gb': round(total_gb, 2),
            'free_gb': round(free_gb, 2),
            'used_gb': round(used_gb, 2),
            'usage_percent': round((used_gb / total_gb) * 100, 2)
        }
    except Exception as e:
        return None

def check_directory_exists(path):
    """Check if a directory exists"""
    return os.path.exists(path) and os.path.isdir(path)

def main():
    cabinet = Cabinet()
    device_name = os.uname().nodename
    
    cabinet.log("Starting comprehensive service check")
    
    # Check Docker containers only on `cloud` (home server)
    if device_name == "cloud":
        docker_services = {
            'immich': 'immich',
            'dawarich': 'dawarich'
        }

        for service_name, container_name in docker_services.items():
            if check_docker_container(container_name):
                cabinet.log(f"✓ {service_name} Docker container is running")
            else:
                cabinet.log(f"✗ {service_name} Docker container is NOT running", level="error")
    else:
        cabinet.log(f"Skipping Docker container checks on device: {device_name}")

    # Check system services
    system_services = ['rustdesk']
    
    if device_name == "cloud": # home server
        for service_name in system_services:
            if check_system_service(service_name):
                cabinet.log(f"✓ {service_name} system service is running")
            else:
                cabinet.log(f"✗ {service_name} system service is NOT running", level="error")
    else:
        cabinet.log(f"Skipping system service checks on device: {device_name}")
    
    # Check disk space
    disk_info = get_disk_usage("/")
    if disk_info:
        cabinet.put("quality", device_name, "free_gb", disk_info['free_gb'])
        timezone = time.tzname[time.daylight] if time.tzname[time.daylight] else "UNKNOWN"
        cabinet.put("quality", device_name, "updated_at", datetime.now().strftime(f"%Y-%m-%d %H:%M:%S {timezone}"))
        cabinet.log(f"✓ Disk space: {disk_info['free_gb']}GB free out of {disk_info['total_gb']}GB total ({disk_info['usage_percent']}% used)")
        
        # Warn if disk usage is high
        if disk_info['usage_percent'] > 90:
            cabinet.log(f"⚠ High disk usage: {disk_info['usage_percent']}%", level="warning")
    else:
        cabinet.log("✗ Failed to get disk usage information", level="error")
    
    # Check syncthing directory structure
    syncthing_base = os.path.expanduser("~/syncthing")
    required_subfolders = ['documents', 'log', 'md', 'music', 'network', 'photos']
    
    if check_directory_exists(syncthing_base):
        cabinet.log(f"✓ Syncthing base directory exists: {syncthing_base}")
        
        for subfolder in required_subfolders:
            subfolder_path = os.path.join(syncthing_base, subfolder)
            if check_directory_exists(subfolder_path):
                cabinet.log(f"✓ Syncthing subfolder exists: {subfolder}")
            else:
                cabinet.log(f"✗ Syncthing subfolder missing: {subfolder}", level="error")
    else:
        cabinet.log(f"✗ Syncthing base directory missing: {syncthing_base}", level="error")
    
    cabinet.log("Service check completed")

if __name__ == "__main__":
    main()