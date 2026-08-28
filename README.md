Senior Project — Stereo Camera Recorder

A portable stereo-camera recording system designed to capture synchronized camera and IMU data, store recordings for later playback, and provide tools for verifying camera synchronization.

The project combines custom 3D-printed hardware, Raspberry Pi-based capture software, a recording viewer, and a screen-flashing synchronization test tool.

Project Overview

The device is designed around a pair of cameras mounted in a custom 3D-printed housing. A Raspberry Pi handles data collection from the cameras and IMU, while the recorded data can later be played back using the Viewer application.

The overall system consists of four major software/hardware components:

CAD — 3D-printable housing and enclosure designs for the physical device.
Capture — Software that runs on the Raspberry Pi and records camera and IMU data.
Viewer — Software for opening and playing back recorded files.
screenFlashBlackWhite — A synchronization-testing tool that rapidly flashes a monitor between black and white so that cameras can be pointed at the screen to visually verify synchronization.

The Pictures directory contains photographs, diagrams, screenshots, and demonstrations of the project.

Hardware
Device Overview

The recorder is built around a Raspberry Pi and a pair of cameras housed inside a custom 3D-printed enclosure.

The Raspberry Pi is responsible for coordinating the recording process and collecting data from the connected sensors and cameras.

The two cameras are mounted together to create the stereo camera system.

Physical Housing

The project uses a custom-designed 3D-printed shell to hold and protect the electronics and cameras.

The housing went through several iterations during development as the physical design was refined.

The enclosure can be viewed from both sides to show how the cameras and internal components fit within the shell.

A version of the device with the top shell removed shows the internal layout.

The CAD design was developed specifically around the project's hardware requirements.

Repository Structure
.
├── CAD
├── Capture
├── Pictures
├── screenFlashBlackWhite
├── Viewer
└── README.md

CAD

The CAD folder contains the 3D models and FreeCAD project files used to design the physical shell of the recorder.

These files are used to create the 3D-printed housing that contains the cameras, Raspberry Pi, and other electronics.

Contents
HousingVersion2.FCStd — FreeCAD project for the second housing design.
HousingVersion2-Bottom.3mf — Bottom portion of the second housing.
HousingVersion2-Cut.3mf — Cut/modified version of the housing for 3D printing.
top.3mf — Top portion of the housing.
RecorderHousing.FCStd — Earlier FreeCAD housing project.
RecorderHousing.3mf — 3MF version of the recorder housing.
RecorderHousing-Bottom.3mf — Bottom portion of the original housing.
*.FCBak — FreeCAD backup files.

The CAD files represent the physical enclosure designs used to manufacture the device.

Capture

The Capture folder contains the software that runs on the Raspberry Pi.

Its primary purpose is data collection. The capture software communicates with the stereo cameras and IMU and coordinates the recording of sensor data.

Main Components
capture.py — Main capture functionality.
stereo.py — Stereo camera recording functionality.
stereoThread.py — Threaded stereo recording implementation.
stereoFiles.py — Functions for managing stereo recording files.
stereoTrigger.py — Camera trigger functionality.
stereoTriggerFiles.py — File handling associated with triggered stereo captures.
imu.py — IMU communication and data collection.
imuThread.py — Threaded IMU data collection.
ov9281_libcamera/ — Camera configuration and trigger utilities for the OV9281 cameras.
pyproject.toml — Python project configuration.
uv.lock — Locked Python dependency versions.
Camera Triggering

The ov9281_libcamera directory contains scripts and configuration used to control the OV9281 cameras and their triggering behavior.

ov9281_libcamera/
├── libcamera-timeout.sh
├── ov9281_trigger
├── timeout.yaml
└── trig_sig_pin_23.sh


These tools are used as part of the low-level camera capture and synchronization setup.

The goal of the Capture software is to make the Raspberry Pi act as the recording computer for the complete sensor system.

Viewer

The Viewer folder contains the software used to play back recorded files after they have been captured.

Rather than requiring the cameras to be connected, the Viewer operates on previously recorded data.

Contents
src/viewer2/ — Viewer application source code.
test.py — Test code for the viewer.
recording.bin — Example or test recording data.
pyproject.toml — Python project configuration.
uv.lock — Locked Python dependency versions.

The viewer provides a way to inspect recorded stereo data after a capture session.

This makes it possible to evaluate recordings without needing to operate the physical recording device.

screenFlashBlackWhite

The screenFlashBlackWhite folder contains a small utility designed to help verify camera synchronization.

The program makes a monitor rapidly alternate between black and white.

The cameras can then be pointed at the flashing screen while recording. By examining the recorded frames, it is possible to determine whether the cameras are seeing the black/white transitions at the same time.

This provides a simple visual synchronization test without requiring specialized synchronization equipment.

Contents
screenFlashBlackWhite/
├── pyproject.toml
├── README.md
├── src
│   └── flash
│       ├── __init__.py
│       └── main.py
└── uv.lock


The main implementation is located in:

src/flash/main.py


The tool is particularly useful during development and hardware testing because synchronization errors can be seen directly in the captured images.

Synchronization Testing

One of the important requirements of a stereo camera system is that both cameras capture images at the same time.

Even a small timing difference can cause problems when the two images are later used as a stereo pair.

The screenFlashBlackWhite tool provides a straightforward way to test this.

The basic procedure is:

Run the screen-flashing tool on a monitor.
Point both cameras at the monitor.
Start a synchronized recording using the Capture system.
Allow the cameras to record several black/white transitions.
Open the recording using the Viewer.
Compare the frames from the two cameras.
Check whether both cameras observe the transitions on the same frames.

The flashing screen acts as a common visual timing reference for both cameras.

Device Development

The physical device went through multiple iterations during development.

An earlier handheld model was used as part of the development process.

The current design evolved into a more refined enclosure containing the stereo cameras and Raspberry Pi.

The device can also be demonstrated rotating to show the overall enclosure and camera placement.

A video demonstration of the device is also included:

Pictures

The Pictures folder contains visual documentation for the project.

Pictures/
├── BothSidesOfShell.jpg
├── CADscreenshot.png
├── Cameras.webp
├── completeDevicePluggedIn.jpg
├── deviceNoTopShell.jpg
├── oldModelHandHeld.png
├── raspberrypi.jpg
├── rotationDemo.mp4
├── shell3dPrinting.jpg
├── ShellVersions.jpg
├── stereoImageViewerGUI.png
└── usage.gif


These assets document the physical construction, CAD design, electronics, camera arrangement, software interface, and device operation.

Typical Workflow

The intended workflow for using the system is:

        ┌─────────────────────┐
        │   Physical Device   │
        │                     │
        │ Raspberry Pi +      │
        │ Stereo Cameras +    │
        │ IMU                 │
        └──────────┬──────────┘
                   │
                   ▼
        ┌─────────────────────┐
        │       Capture       │
        │                     │
        │ Collect camera and  │
        │ IMU data            │
        └──────────┬──────────┘
                   │
                   ▼
        ┌─────────────────────┐
        │   Recorded Files    │
        └──────────┬──────────┘
                   │
                   ▼
        ┌─────────────────────┐
        │       Viewer        │
        │                     │
        │ Playback recordings │
        └─────────────────────┘


For synchronization testing, the workflow additionally includes:

        ┌──────────────────────────┐
        │ screenFlashBlackWhite    │
        │                          │
        │ Flash monitor            │
        │ black ↔ white            │
        └────────────┬─────────────┘
                     │
                     ▼
              ┌─────────────┐
              │ Stereo      │
              │ Cameras     │
              └──────┬──────┘
                     │
                     ▼
              ┌─────────────┐
              │ Capture     │
              └──────┬──────┘
                     │
                     ▼
              ┌─────────────┐
              │ Viewer      │
              │             │
              │ Compare     │
              │ transitions │
              └─────────────┘

Software Projects

Each software component is maintained as its own Python project and includes a pyproject.toml and uv.lock.

Capture

Runs on the Raspberry Pi and handles:

Stereo camera capture
Camera triggering
IMU data collection
Threaded sensor acquisition
Recording data to files
Viewer

Runs on a computer and handles:

Loading recorded files
Playing back stereo recordings
Inspecting captured data
screenFlashBlackWhite

Runs a flashing black-and-white display used for:

Camera synchronization testing
Visual timing verification
Debugging synchronization problems
Development Goals

The overall goal of the project is to provide a compact stereo recording platform capable of collecting synchronized camera and motion data in a portable form factor.

The combination of:

Custom 3D-printed hardware
Raspberry Pi data collection
Hardware camera triggering
IMU recording
Stereo playback
Visual synchronization testing

creates a complete pipeline from physical capture through post-recording analysis.

Project Demonstration

The finished device combines the custom housing, Raspberry Pi, and stereo camera system into a single portable unit.

The system can be handled and operated as a standalone recording device.

The custom shell provides the mechanical structure necessary to keep the cameras and electronics positioned correctly.

The Viewer software then provides a way to inspect the resulting stereo recordings.

Together, the hardware and software form the complete senior project.