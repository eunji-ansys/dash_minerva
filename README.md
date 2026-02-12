# Minerva File Management Dashboard

A Python-based web application built with **Dash** for managing and downloading files from the Minerva SPDM system. It features a responsive UI, pattern-matching callbacks, and secure file transfer mechanisms.

---

## 🚀 Key Features
* **OData API Integration**: Fetches comprehensive data models including **Projects, Simulation Requests, and Work Requests** along with their hierarchical file structures directly from Minerva via OData API.
* **Dynamic File Table**: Automatically generates a tree-like table structure from Minerva metadata.


---

## 🛠 Tech Stack

* **Frontend**: Dash, Dash Bootstrap Components (DBC)
* **Backend**: Python 3.x, Flask (underlying Dash)
* **Communication**: Requests (HTTP/REST)

---

## 📂 Project Structure



```text
.
├── assets/
│   └── icons/          # SVG icons (archive, download, eye, etc.)
├── logic/
    ├── core/                   # Low-level engines for system communication
    │   └── minerva/            # Minerva-specific core modules
    │       ├── auth.py         # Authentication logic and credential handling
    │       ├── cli.py          # Functional wrapper for Minerva CLI execution
    │       └── odata.py        # REST API (OData) communication logic
    ├── services/               # High-level business logic & client implementations
    │   ├── dummy_client.py     # Mock client for testing and development
    │   └── vd_client.py        # Main client for specific business services (e.g., VD)
    └── utils/                  # Common utilities and helper functions
        └── decorators.py       # Reusable decorators (e.g., logging, timing)
dash_minerva.py             # Main entry point (Dash application)
.env                        # Environment variables (instance URL, DB name, etc.)
```

## ⚙️ Installation & Setup

Follow these steps to set up the development environment on your local machine.

### 1. Clone the Repository
First, clone the project to your local directory:
```
$git clone <your-repository-url>
$ cd dash_minerva
```

### 2. Create a Virtual Environment
It is highly recommended to use a virtual environment to manage dependencies:
#### Create the environment
```
$ python -m venv .venv
```
#### Activate the environment

```
# On Windows:
$ .venv\Scripts\activate

# On Mac/Linux:
$ source .venv/bin/activate
```

### 3. Install Required Packages
Install all necessary libraries including Dash, OData-related tools, and data processing packages:
```
(.venv)$ pip install -r requirements.txt
```

### 4. Configure Environment Variables
The application requires sensitive credentials to access the Minerva OData API. Create a `.env` file in the root directory and add the following:
```
MINERVA_URL=https://your-minerva-server.com
MINERVA_USER=your_id
MINERVA_PASS=your_password
TEMP_DOWNLOAD_PATH=./temp_downloads
```
*Note: Ensure .env is listed in your .gitignore to prevent leaking credentials.*

## 🏃 Execution

Once the installation is complete and the `.env` file is configured, you can run the dashboard using the following command:

```
(.venv)$ python dash_minerva.py
```

After running the command:
1. Open your web browser.
2. Go to http://127.0.0.1:8050
3. You should see the Minerva File Management Dashboard.

*Note: If you are running the app on a server, ensure that port 8050 is open in your firewall settings.*