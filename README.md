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
│   ├── core/           # Core modules (auth, cli_executor, odata)
│   ├── services/       # Service layer (minerva_client, dummy_client)
│   └── utils/          # Utility functions and decorators
├── .gitignore          # Git exclusion rules
├── dash_minerva.py     # Main application entry point
├── README.md           # Project documentation
└── requirements.txt    # Python package dependencies
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
# Create the environment
```
$ python -m venv .venv

# Activate the environment
# On Windows:
$ .venv\Scripts\activate
# On Mac/Linux:
$ source .venv/bin/activate
```

### 3. Install Required Packages
Install all necessary libraries including Dash, OData-related tools, and data processing packages:
```
$ pip install -r requirements.txt
```

### 4. Configure Environment Variables
The application requires sensitive credentials to access the Minerva OData API. Create a `.env` file in the root directory and add the following:
```
MINERVA_URL=[https://your-minerva-server.com](https://your-minerva-server.com)
MINERVA_USER=your_id
MINERVA_PASS=your_password
TEMP_DOWNLOAD_PATH=./temp_downloads
```
*Note: Ensure .env is listed in your .gitignore to prevent leaking credentials.*