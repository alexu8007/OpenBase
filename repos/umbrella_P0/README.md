# Umbrella Reminder

A command-line tool to check for rain and remind you to bring an umbrella. This script scrapes the National Weather Service for forecast information.

## Installation

1.  **Clone the repository (or download the source code):**
    ```bash
    git clone <repository-url>
    cd umbrella-reminder
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install the package:**
    This will install the script and its dependencies.
    ```bash
    pip install .
    ```

## Usage

Once installed, you can run the tool from your terminal.

### Check the forecast for a specific location:
Provide the latitude and longitude.

```bash
umbrella-reminder --lat 34.0522 --lon -118.2437
```

### Get verbose output:
Use the `-v` or `--verbose` flag to see debug-level logs, which can be helpful for troubleshooting.
```bash
umbrella-reminder --lat 34.0522 --lon -118.2437 --verbose
```

### Default Location:
If you run the command without arguments, it will default to New York, NY.
```bash
umbrella-reminder
``` 