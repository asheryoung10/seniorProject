Senior Project
Overview

This project is a portable stereo vision recording device designed to capture synchronized stereo imagery and motion data.

The system combines a Raspberry Pi, stereo cameras, an IMU, custom 3D-printed housing, and software for recording and viewing captured data.

Device

The completed device with the Raspberry Pi, cameras, housing, and electronics assembled.

The Raspberry Pi used as the main computer for the device.

The stereo camera setup.

The device with the top portion of the housing removed.

Both sides of the 3D-printed device shell.

Housing Design

The housing was designed specifically for the electronics and stereo camera configuration.

CAD design of the housing.

Different iterations of the device housing.

The housing being 3D printed.

Development

An earlier version of the device was designed as a handheld system.

Early handheld prototype.

The final design moved toward a more compact enclosure that houses the cameras, Raspberry Pi, and supporting electronics.

Stereo Recording

The system uses two synchronized cameras to capture stereo imagery.

The stereo image viewer used to inspect captured imagery.

Demonstration of the system in use.

Rotation Demonstration

A demonstration of the physical device rotating is available here:

View the rotation demonstration video

Software

The repository contains several components:

Capture

The Capture directory contains the software responsible for capturing stereo images and IMU data.

Capture/
├── capture.py
├── imu.py
├── imuThread.py
├── stereo.py
├── stereoThread.py
├── stereoFiles.py
├── stereoTrigger.py
├── stereoTriggerFiles.py
└── ov9281_libcamera/

Viewer

The Viewer directory contains software for viewing recorded data.

Viewer/
├── src/
├── test.py
├── recording.bin
└── pyproject.toml

Screen Flash

The screenFlashBlackWhite directory contains the screen flashing component used by the system.

screenFlashBlackWhite/
├── src/
├── pyproject.toml
└── uv.lock

CAD

The CAD directory contains the FreeCAD and 3MF files used to design and manufacture the housing.

CAD/
├── HousingVersion2.20260817-162316.FCBak
├── HousingVersion2-Bottom.3mf
├── HousingVersion2-Cut.3mf
├── HousingVersion2.FCStd
├── RecorderHousing.20260810-164046.FCBak
├── RecorderHousing.3mf
├── RecorderHousing-Bottom.3mf
├── RecorderHousing.FCStd
└── top.3mf

Project Structure
seniorProject/
├── CAD/
├── Capture/
├── Pictures/
├── Viewer/
├── screenFlashBlackWhite/
└── README.md

Media

The project media is stored in the Pictures directory.

BothSidesOfShell.jpg — housing shell
CADscreenshot.png — CAD design
Cameras.webp — stereo cameras
completeDevicePluggedIn.jpg — completed device
deviceNoTopShell.jpg — device without top shell
oldModelHandHeld.png — early handheld design
raspberrypi.jpg — Raspberry Pi
rotationDemo.mp4 — rotation demonstration
shell3dPrinting.jpg — 3D printing process
ShellVersions.jpg — housing iterations
stereoImageViewerGUI.png — viewer interface
usage.gif — usage demonstration
