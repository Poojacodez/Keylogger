# Keylogger
# This Windows Keylogger Project

This project is a Python-based keylogger application designed specifically for Windows systems. It serves as an educational demonstration to understand how keyboard monitoring works at a technical level.

## Core Functionality

This keylogger captures keyboard input with these main features:

1. **Keystroke Tracking**: The system implements complete keyboard monitoring that records both when keys are pressed and released, along with precise timestamps.

2. **Security Features**: The project incorporates Fernet symmetric encryption to protect the logged data, which can be toggled on or off through configuration.

3. **Customizable Settings**: A JSON configuration system allows adjustments to:
   - How often reports are generated
   - Whether encryption is used
   - Where reports are saved
   - Maximum file sizes before archiving

4. **Dependency Handling**: The program automatically checks for required Python libraries and installs them if missing, making setup simpler.

5. **System Profiling**: The keylogger collects basic system information including the computer's hostname, IP, username, and OS details.

6. **Comprehensive Reporting**: 
   - The system implements periodic report generation at configurable intervals
   - When stopped, it creates a detailed final report
   - Reports come in both technical (JSON) and human-readable (HTML) formats

7. **Easy Control**: A simple Ctrl+X shortcut stops recording when needed.

## Output Generated

When running this keylogger, it produces:

1. **Text Log Files**: Raw keystroke data with timestamps showing exactly when each key was pressed or released.

2. **Encrypted Archives**: When encryption is enabled, logs are secured with encryption before storage.

3. **Structured JSON Reports**: Upon completion, a comprehensive JSON file is generated containing all system information and keystroke data.

4. **Visual HTML Reports**: For easier analysis, a formatted HTML page is created with:
   - A clean section showing system details
   - Well-organized tables of all keystroke activity
   - Proper formatting to make large amounts of data manageable

5. **Status Updates**: The console displays operation status throughout runtime.

6. **Detailed Logging**: For troubleshooting, everything is logged to "keylogger.log" for diagnostic purposes.

*This project was developed solely as an educational tool to understand input monitoring techniques and encryption implementation in Python.*
