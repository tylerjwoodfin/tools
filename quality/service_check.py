#!/usr/bin/env python3
"""
Service check script to monitor Docker containers, system services, and disk space.
"""
import subprocess
import os
from datetime import datetime
import time
from cabinet import Cabinet


def run_command(command):
    """Run a shell command and return the result"""
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, check=False
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except Exception as e:  # pylint: disable=broad-exception-caught
        return False, "", str(e)


def check_docker_container(container_name):
    """Check if a Docker container is running"""
    success, output, _ = run_command(
        f"docker ps --filter name={container_name} --format '{{{{.Names}}}}'"
    )
    if success and container_name in output:
        return True
    return False


def check_system_service(service_name):
    """Check if a system service is running"""
    success, output, _ = run_command(f"systemctl is-active {service_name}")
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
            "total_gb": round(total_gb, 2),
            "free_gb": round(free_gb, 2),
            "used_gb": round(used_gb, 2),
            "usage_percent": round((used_gb / total_gb) * 100, 2),
        }
    except Exception:  # pylint: disable=broad-exception-caught
        return None


def check_directory_exists(path):
    """Check if a directory exists"""
    return os.path.exists(path) and os.path.isdir(path)


def ping_host(hostname):
    """Ping a host and return success status"""
    success, _, _ = run_command(f"ping -c 1 -W 3 {hostname}")
    return success


def check_dawarich_recent_points():
    """Check if new points have been added to Dawarich within the past 24 hours"""
    # First check if the database container is running
    if not check_docker_container("dawarich_db"):
        return False, "Dawarich database container is not running"
    
    # Query for points created in the last 24 hours
    # Using docker exec to query the PostgreSQL database
    query = (
        "SELECT COUNT(*) FROM points "
        "WHERE created_at >= NOW() - INTERVAL '24 hours';"
    )
    
    command = (
        f'docker exec dawarich_db psql -U postgres -d dawarich_development '
        f'-t -c "{query}"'
    )
    
    success, output, error = run_command(command)
    
    if not success:
        return False, f"Failed to query database: {error}"
    
    try:
        count = int(output.strip())
        return True, count
    except ValueError:
        return False, f"Invalid response from database: {output}"

def main():
    """Main function to perform comprehensive service check"""
    cabinet = Cabinet()
    device_name = os.uname().nodename

    cabinet.log("Starting comprehensive service check")

    # Check Docker containers only on `cloud` (home server)
    if device_name == "cloud":
        docker_services = {"immich": "immich", "dawarich": "dawarich"}

        for service_name, container_name in docker_services.items():
            if check_docker_container(container_name):
                cabinet.log(f"✓ {service_name} Docker container is running")
            else:
                cabinet.log(
                    f"✗ {service_name} Docker container is NOT running", level="error"
                )
        
        # Check for recent Dawarich points
        success, result = check_dawarich_recent_points()
        if success:
            if isinstance(result, int) and result > 0:
                cabinet.log(
                    f"{result} new point(s) added in the past 24 hours"
                )
            else:
                cabinet.log(
                    "No new points added in the past 24 hours",
                    level="warning"
                )
        else:
            cabinet.log(
                f"Failed to check recent points - {result}",
                level="error"
            )
    else:
        cabinet.log(f"Skipping Docker container checks on device: {device_name}")

    # Check system services
    system_services = ["rustdesk"]

    if device_name == "cloud":  # home server
        for service_name in system_services:
            if check_system_service(service_name):
                cabinet.log(f"✓ {service_name} system service is running")
            else:
                cabinet.log(
                    f"✗ {service_name} system service is NOT running", level="error"
                )
    else:
        cabinet.log(f"Skipping system service checks on device: {device_name}")

    # Check disk space
    disk_info = get_disk_usage("/")
    if disk_info:
        cabinet.put("quality", device_name, "free_gb", disk_info["free_gb"])
        timezone = (
            time.tzname[time.daylight] if time.tzname[time.daylight] else "UNKNOWN"
        )
        timestamp = datetime.now().strftime(f"%Y-%m-%d %H:%M:%S {timezone}")
        cabinet.put("quality", device_name, "updated_at", timestamp)
        cabinet.log(
            f"✓ Disk space: {disk_info['free_gb']}GB free out of "
            f"{disk_info['total_gb']}GB total ({disk_info['usage_percent']}% used)"
        )

        # Warn if disk usage is high
        if disk_info["usage_percent"] > 90:
            cabinet.log(
                f"⚠ High disk usage: {disk_info['usage_percent']}%", level="warning"
            )
    else:
        cabinet.log("✗ Failed to get disk usage information", level="error")

    # Check syncthing directory structure
    syncthing_base = os.path.expanduser("~/syncthing")
    required_subfolders = ["documents", "log", "md", "music", "network", "photos"]

    if check_directory_exists(syncthing_base):
        cabinet.log(f"✓ Syncthing base directory exists: {syncthing_base}")

        for subfolder in required_subfolders:
            subfolder_path = os.path.join(syncthing_base, subfolder)
            if check_directory_exists(subfolder_path):
                cabinet.log(f"✓ Syncthing subfolder exists: {subfolder}")
            else:
                cabinet.log(
                    f"✗ Syncthing subfolder missing: {subfolder}", level="error"
                )
    else:
        cabinet.log(
            f"✗ Syncthing base directory missing: {syncthing_base}", level="error"
        )

    # Ping external hosts
    external_hosts = ["git.tyler.cloud", "photos.tyler.cloud"]

    for host in external_hosts:
        if ping_host(host):
            cabinet.log(f"✓ Ping to {host} successful")
        else:
            cabinet.log(f"✗ Ping to {host} failed", level="error")

    cabinet.log("Service check completed")


if __name__ == "__main__":
    main()
