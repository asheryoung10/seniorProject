Senior Project — Stereo Data Recorder

A Raspberry Pi-based stereo imaging and sensor recording system designed to collect synchronized camera and IMU data, save the recordings to an SSD, and provide a desktop viewer for reviewing the collected data.

Overview

This project consists of three main software components and a custom 3D-printed enclosure:

Capture — Runs on the Raspberry Pi and controls the cameras and IMU while collecting data.
Viewer — Desktop software for opening and reviewing previously recorded data.
screenFlashBlackWhite — Provides a flashing black/white screen used as part of the capture system.
CAD — Contains the CAD models and 3D-printable files for the device enclosure.

The overall workflow is:

                    ┌─────────────────────┐
                    │     Raspberry Pi    │
                    │                     │
                    │  Stereo Cameras     │
                    │       +             │
                    │       IMU           │
                    └──────────┬──────────┘
                               │
                               │ Capture
                               ▼
                    ┌─────────────────────┐
                    │        SSD          │
                    │                     │
                    │  Recorded sensor    │
                    │  + stereo data      │
                    └──────────┬──────────┘
                               │
                               │ Transfer / access
                               ▼
                    ┌─────────────────────┐
                    │       Viewer        │
                    │                     │
                    │ Review recordings   │
                    │ and stereo images   │
                    └─────────────────────┘

Hardware

The device uses a Raspberry Pi as the main computer, with stereo cameras and an IMU mounted inside a custom enclosure.

The enclosure was designed specifically for the electronics and cameras and is 3D printed.

Capture

The Capture/ directory contains the software intended to run on the Raspberry Pi.

Capture/
├── capture.py
├── imu.py
├── imuThread.py
├── stereo.py
├── stereoThread.py
├── stereoFiles.py
├── stereoTrigger.py
├── stereoTriggerFiles.py
├── ov9281_libcamera/
├── src/
├── pyproject.toml
└── uv.lock


The capture software is responsible for collecting data from the stereo camera system and IMU.

The Raspberry Pi stores the collected recordings on an SSD rather than keeping large datasets in the Git repository.

Camera system

The stereo camera setup allows the system to capture images from two cameras at the same time.

The project also contains scripts and configuration for working with the OV9281 cameras through libcamera.

Capture/ov9281_libcamera/
├── libcamera-timeout.sh
├── ov9281_trigger
├── timeout.yaml
└── trig_sig_pin_23.sh

IMU

The IMU collection code is separated into its own modules and thread so that sensor data can be collected alongside the camera data.

imu.py
imuThread.py

Viewer

The Viewer/ directory contains the software used to view previously recorded data.

Viewer/
├── pyproject.toml
├── README.md
├── src/
│   └── viewer2/
│       └── __init__.py
├── test.py
└── uv.lock


The viewer allows recorded stereo data to be opened and inspected after it has been collected by the Raspberry Pi.

The viewer is intended to make the data collected in the field easier to inspect without needing to run the capture hardware.

Screen Flash

The screenFlashBlackWhite/ directory contains a small application used to display a flashing black-and-white screen.

screenFlashBlackWhite/
├── pyproject.toml
├── README.md
├── src/
│   └── flash/
│       ├── __init__.py
│       └── main.py
└── uv.lock

CAD

The CAD/ directory contains the enclosure designs and 3D-printable models.

Current CAD files include:

HousingVersion2.FCStd
HousingVersion2-Bottom.3mf
HousingVersion2-Cut.3mf
RecorderHousing.FCStd
RecorderHousing.3mf
RecorderHousing-Bottom.3mf
top.3mf

The .FCStd files are FreeCAD source files, while .3mf files can be used for 3D printing.

FreeCAD backup files (.FCBak) are not tracked by Git.

Physical Design

The enclosure went through multiple design iterations during development.

The final enclosure is designed to hold the cameras and electronics while providing a compact, portable recording system.

Usage
1. Capture data

Connect the Raspberry Pi to the camera system, IMU, and SSD.

Run the capture software on the Raspberry Pi:

cd Capture
uv run capture.py


The exact capture command may depend on the current configuration and which capture mode is being used.

Captured data should be stored on the SSD rather than committed to Git.

2. Transfer recordings

After collecting data, connect or transfer the SSD data to the computer running the viewer.

Large recordings should remain outside of the Git repository.

3. View recordings

From the Viewer/ directory, install the project dependencies and run the viewer according to its configuration.

cd Viewer
uv sync


The viewer can then be used to inspect previously collected recordings.

Development

This project uses Python and uv for dependency management.

Each Python component contains its own pyproject.toml and uv.lock.

For example:

cd Capture
uv sync


or:

cd Viewer
uv sync

Repository Structure
seniorProject/
│
├── CAD/                    # CAD source and 3D-print files
│
├── Capture/                # Raspberry Pi data collection software
│   ├── capture.py
│   ├── imu.py
│   ├── imuThread.py
│   ├── stereo.py
│   ├── stereoThread.py
│   ├── stereoFiles.py
│   ├── stereoTrigger.py
│   ├── stereoTriggerFiles.py
│   └── ov9281_libcamera/
│
├── Pictures/               # Project documentation and media
│
├── Viewer/                 # Recording viewer software
│
├── screenFlashBlackWhite/  # Screen flashing utility
│
└── README.md

Project Media

A demonstration of the device and software is included in the Pictures/ directory.

Additional project documentation includes photos of the physical device, CAD iterations, the Raspberry Pi, camera setup, and the viewer interface.

Status

This project is a senior project and is under active development.

The primary system consists of:

Raspberry Pi data acquisition
Synchronized stereo camera capture
IMU data collection
SSD-based recording storage
Desktop recording viewer
Custom 3D-printed enclosure

License

Add the project's license here if/when one is selected.
