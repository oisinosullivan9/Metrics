# Metrics
CS4447 Context of the Code Project
- Oisin O Sullivan - 22368493

## Overview
This project is a system performance and temperature monitoring application that consists of 5 main components:
- A flask based web server for receiving, and storing metrics
- a metrics collection agent for gathering system performance data
- a UDP listener for esp32 temperature data
- an uploader queue which sends metriucs to the server in specific time intervals
- A Dash interactive dashboard for visualizing metrics

## Features
- PC Performance tracking
- ESP32 temperature monitoring
- Interactive dashboard

## Setup and Installation

### Prerequisites
- Python 3
- pip package installer
- to recieve metrics from esp32, you will need to clone this repository: https://github.com/oisinosullivan9/embedded_assignment.git 

### Setup

1. clone the repository:
     ```bash
    git clone https://github.com/oisinosullivan9/Metrics.git
    ```

2. install dependencies
    ```bash
    pip install -r requirements.txt
    ```

3. run the flask  server:
    ```bash
    python main.py
    ```

4. run the pc collector:
    ```bash
    python pc_metrics.py
    ```

5. run the esp32 collector:
    ```bash
    python esp32_metrics.py
    ```
    note: you will need to have embedded sytem setup and running for this

6. run the uploader queue:
    ```bash
    python uploader_queue.py
    ```

## Disclaimer
I used Render to deploy this project, so you will have to modify config.yaml to deploy it locally