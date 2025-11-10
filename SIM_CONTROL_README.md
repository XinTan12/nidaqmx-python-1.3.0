# SIM Hardware Synchronization Control System

## Overview

This system provides **microsecond-precision hardware-timed synchronization** for Structured Illumination Microscopy (SIM) using National Instruments DAQ hardware and Python.

It controls three devices in precise synchronization:
1. **Hamamatsu Camera** - External level trigger mode
2. **Laser** - Trigger-based activation
3. **SLM (Spatial Light Modulator)** - Three-signal control (Enable, Trigger, Finish)

## Key Features

- **Hardware-timed control** - True microsecond precision using NI DAQ internal timebase
- **Synchronized triggering** - Camera, laser, and SLM triggers fire simultaneously
- **Precise exposure control** - Programmable exposure time with microsecond accuracy
- **9-frame SIM patterns** - Standard SIM imaging with configurable frame counts
- **Camera ready monitoring** - High-speed analog input monitoring for synchronization
- **Flexible configuration** - Easy parameter adjustment for different imaging modes

## Files

- **`sim_control_synchronized.py`** - Main control class implementation
- **`sim_control_config_example.py`** - Configuration examples and testing utilities
- **`SIM_CONTROL_README.md`** - This documentation file

## Hardware Requirements

### NI DAQ Device
- Minimum requirements:
  - 5 digital output lines (for triggers)
  - 1 analog input channel (for camera ready)
  - Hardware-timed operations support
  - Sample clock rate ≥ 1 MHz
- Recommended: NI USB-6343, NI PCIe-6321, or similar

### Connections

#### Digital Outputs (NI DAQ → Devices)

| DAQ Port/Line | Device Connection | Signal Type | Description |
|---------------|-------------------|-------------|-------------|
| `Dev1/port0/line0` | Camera Trigger | Level (Active High) | Triggers camera exposure |
| `Dev1/port0/line1` | Laser Trigger | Level (Active High) | Activates laser output |
| `Dev1/port0/line2` | SLM Enable | Level (Active High) | Enables SLM for loop |
| `Dev1/port0/line3` | SLM Trigger | Edge (Rising) | Triggers SLM pattern change |
| `Dev1/port0/line4` | SLM Finish | Edge (Rising) | Signals end of pattern |

#### Analog Input (Device → NI DAQ)

| Device Output | DAQ Input | Signal Range | Description |
|---------------|-----------|--------------|-------------|
| Camera Ready | `Dev1/ai0` | 0-10V | High (>2.5V) when camera ready |

## Software Requirements

```bash
# Python 3.7+
pip install nidaqmx
pip install numpy
```

## Quick Start

### 1. Basic Usage

```python
from sim_control_synchronized import SIMController

# Create controller with basic settings
with SIMController(
    device_name='Dev1',
    exposure_time_us=10000,  # 10ms exposure
    frames_per_loop=9,       # 9 frames per SIM pattern
    num_loops=1              # Single acquisition
) as controller:
    controller.run_acquisition()
```

### 2. Run Examples

```bash
python sim_control_config_example.py
```

This launches an interactive menu with:
- Multiple acquisition scenarios
- Hardware testing utilities
- Configuration guide

## Configuration Parameters

### SIMController Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `device_name` | str | `"Dev1"` | NI DAQ device identifier |
| `exposure_time_us` | float | `10000` | Exposure time in microseconds |
| `frames_per_loop` | int | `9` | Frames per SIM pattern cycle |
| `num_loops` | int | `1` | Number of complete acquisition loops |
| `sample_rate` | float | `1000000` | DAQ sample clock rate (Hz) |

### Timing Specifications

- **Resolution**: 1 microsecond (at 1 MHz sample rate)
- **Precision**: < 1 microsecond jitter (hardware-timed)
- **Range**: Exposure time from 10 μs to several seconds
- **Frame rate**: Limited by camera readout time

## External Device Configuration

### Camera (Hamamatsu HCImage Software)

1. Set **Trigger Mode** to "External Level Trigger"
2. Set **Trigger Polarity** to "Active High"
3. Configure **Exposure Control** to use external trigger duration
4. Configure frame size, binning, and gain as needed
5. Enable **Trigger Ready** output signal

### Laser Controller

1. Set **Trigger Mode** to "External"
2. Set **Trigger Polarity** to "Active High"
3. Adjust laser **Power** to desired level
4. Ensure safety interlocks are satisfied
5. Configure for level-triggered operation (not edge)

### SLM Controller

According to the J2 Synchronization Port specification:

1. **SPI_0 (Enable Signal)**: Connect to `line2`
   - Level-triggered, active high
   - High during entire 9-frame loop

2. **SPI_1 (Trigger Signal)**: Connect to `line3`
   - Edge-triggered, rising edge
   - Triggers pattern change

3. **SPI_2 (Finish Signal)**: Connect to `line4`
   - Edge-triggered, rising edge
   - Terminates current pattern at next safe point

4. Configure 9 SIM patterns in SLM software
5. Set to hardware-controlled pattern sequencing

## Timing Diagrams

### Single Frame Timing

```
Time (μs):      0          5000        10000       10100

Camera Trig:    |‾‾‾‾‾‾‾‾‾‾‾‾‾‾|________________
Laser Trig:     |‾‾‾‾‾‾‾‾‾‾‾‾‾‾|________________
SLM Enable:     |‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
SLM Trigger:    |‾|_____________________________
SLM Finish:     ______________|‾|_______________

                <-- Exposure -->
```

### 9-Frame Loop Timing

```
Frame:          1      2      3      4      5      6      7      8      9

SLM Enable:     |‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾|_____
Cam/Laser:      |‾‾‾||‾‾‾||‾‾‾||‾‾‾||‾‾‾||‾‾‾||‾‾‾||‾‾‾||‾‾‾|_____
SLM Trigger:    |‾||‾||‾||‾||‾||‾||‾||‾||‾||‾|___________________
SLM Finish:     __|‾||‾||‾||‾||‾||‾||‾||‾||‾|___________________
Cam Ready:      __|‾‾|_|‾‾|_|‾‾|_|‾‾|_|‾‾|_|‾‾|_|‾‾|_|‾‾|_|‾‾|_
```

## Usage Examples

### Example 1: Standard SIM Acquisition

```python
from sim_control_synchronized import SIMController

# Standard 9-frame SIM with 20ms exposure
with SIMController(
    device_name='Dev1',
    exposure_time_us=20000,
    frames_per_loop=9,
    num_loops=1
) as controller:
    success = controller.run_acquisition()
    print(f"Acquisition {'successful' if success else 'failed'}!")
```

### Example 2: High-Speed Time-Lapse

```python
# Fast time-lapse: 100 time points with 1ms exposure
with SIMController(
    device_name='Dev1',
    exposure_time_us=1000,   # 1ms exposure
    frames_per_loop=9,
    num_loops=100            # 100 time points
) as controller:
    controller.run_acquisition()
```

### Example 3: Manual Step-by-Step Control

```python
controller = SIMController(
    device_name='Dev1',
    exposure_time_us=10000,
    frames_per_loop=9,
    num_loops=1
)

try:
    # Setup hardware
    controller.setup_tasks()

    # Start monitoring
    controller.ai_task.start()

    # Wait for camera ready
    if controller.wait_for_camera_ready():
        # Execute acquisition
        controller.execute_single_loop()

finally:
    controller.cleanup()
```

### Example 4: Testing Hardware Connections

```python
# Test digital outputs
from sim_control_config_example import test_digital_outputs
test_digital_outputs()

# Test analog input
from sim_control_config_example import test_analog_input
test_analog_input()
```

## Troubleshooting

### Camera Not Triggering

**Symptoms**: No camera exposure despite control signal

**Solutions**:
1. Verify cable connection to `Dev1/port0/line0`
2. Check camera is in "External Level Trigger" mode
3. Confirm trigger voltage (should be 3.3V or 5V logic level)
4. Use oscilloscope to verify trigger signal
5. Check camera trigger polarity setting

### SLM Not Updating Patterns

**Symptoms**: SLM shows same pattern or no pattern changes

**Solutions**:
1. Verify all three SLM connections (Enable, Trigger, Finish)
2. Check SLM software is in external control mode
3. Confirm edge trigger polarity (rising edge)
4. Verify pattern sequence is loaded in SLM software
5. Check SLM documentation for J2 connector pinout

### Laser Not Firing

**Symptoms**: No laser output during acquisition

**Solutions**:
1. Check connection to `Dev1/port0/line1`
2. Verify laser external trigger mode is enabled
3. Confirm laser safety interlocks are satisfied
4. Check laser power setting is above threshold
5. Use power meter to verify any output

### Camera Ready Timeout

**Symptoms**: "Camera ready signal timeout" error

**Solutions**:
1. Check analog input connection (`Dev1/ai0`)
2. Verify camera ready signal is 0-10V range
3. Measure ready signal voltage with multimeter
4. Adjust `READY_SIGNAL_THRESHOLD` if needed (default 2.5V)
5. Increase timeout in `wait_for_camera_ready()` call
6. Ensure camera is powered on and initialized

### Timing Jitter or Inconsistency

**Symptoms**: Inconsistent frame timing or exposure

**Solutions**:
1. Use hardware-timed operations (already implemented)
2. Increase sample rate for better resolution
3. Check DAQ device specifications for timebase accuracy
4. Verify no other software is using DAQ device
5. Ensure adequate system resources (CPU, memory)

## Advanced Usage

### Custom Waveform Generation

To modify the timing pattern, edit the `generate_frame_waveform()` method:

```python
def generate_frame_waveform(self) -> np.ndarray:
    # Modify timing parameters here
    trigger_high_samples = self.exposure_samples
    trigger_edge_samples = 10  # Adjust edge pulse width
    post_exposure_samples = 100  # Adjust inter-frame delay

    # Custom waveform logic...
```

### Hardware-Timed Start Trigger

Add external start trigger for multi-device synchronization:

```python
# In setup_tasks() method, add:
self.do_task.triggers.start_trigger.cfg_dig_edge_start_trig(
    trigger_source="/Dev1/PFI0",
    trigger_edge=Edge.RISING
)
```

### Exporting Sample Clock

Share timing with other devices:

```python
# Export sample clock for external synchronization
self.do_task.export_signals.samp_clk_output_term = "/Dev1/PFI5"
```

### Callback-Based Data Acquisition

For real-time data processing:

```python
def callback(task_handle, event_type, num_samples, callback_data):
    # Process data in real-time
    data = task.read(number_of_samples_per_channel=num_samples)
    # Your processing code here
    return 0

# Register callback
task.register_every_n_samples_acquired_into_buffer_event(1000, callback)
```

## Performance Optimization

### Maximizing Timing Precision

1. **Use 10 MHz sample rate** (if hardware supports):
   ```python
   sample_rate=10000000  # 0.1 μs resolution
   ```

2. **Minimize software overhead**:
   - Use hardware triggers instead of polling
   - Pre-allocate buffers
   - Avoid unnecessary data processing in loop

3. **Optimize buffer sizes**:
   ```python
   self.ai_task.in_stream.input_buf_size = 10000
   self.do_task.out_stream.output_buf_size = 10000
   ```

### Maximizing Frame Rate

1. Reduce exposure time (limited by signal intensity)
2. Optimize camera readout speed in HCImage
3. Use hardware ready signal instead of software polling
4. Minimize inter-frame delay in waveform generation

## API Reference

### SIMController Class

#### Methods

**`__init__(device_name, exposure_time_us, frames_per_loop, num_loops, sample_rate)`**
- Initialize controller with configuration parameters

**`setup_tasks()`**
- Configure NI DAQ tasks for digital output and analog input

**`generate_frame_waveform() -> np.ndarray`**
- Generate digital waveform for single frame acquisition
- Returns: 5×N array of digital output states

**`generate_loop_waveform() -> Tuple[np.ndarray, int]`**
- Generate complete waveform for 9-frame loop
- Returns: (waveform array, samples per frame)

**`wait_for_camera_ready(timeout) -> bool`**
- Monitor analog input for camera ready signal
- Returns: True if ready detected, False if timeout

**`execute_single_loop() -> bool`**
- Execute one complete acquisition loop (9 frames)
- Returns: True if successful, False otherwise

**`run_acquisition() -> bool`**
- Execute complete acquisition sequence for all loops
- Returns: True if all loops completed successfully

**`cleanup()`**
- Release hardware resources and close tasks

## Technical Details

### Hardware Timing Architecture

The system uses NI DAQ's hardware-timed digital output with buffered generation:

1. **Waveform pre-generation**: All trigger patterns are calculated before acquisition
2. **Hardware buffering**: Waveform loaded to DAQ's onboard memory
3. **Hardware clocking**: Internal timebase controls output timing
4. **Zero software latency**: No software loop delays affect timing

### Timing Precision Analysis

| Component | Precision | Notes |
|-----------|-----------|-------|
| Exposure time | < 1 μs | Hardware-timed, depends on sample rate |
| Trigger jitter | < 1 μs | Limited by DAQ timebase |
| Frame interval | ~100 μs | Software overhead in camera ready detection |
| Loop start | ~1 ms | Camera initialization time |

### Memory Requirements

For 1 MHz sample rate, 9 frames, 10ms exposure:
- Waveform buffer: ~450 KB (5 channels × 90,000 samples × 1 byte)
- AI buffer: ~40 KB (10,000 samples × 8 bytes)
- Total: < 1 MB per loop

## Safety Considerations

1. **Laser safety**: Ensure all interlocks are functional
2. **Electrical safety**: Verify voltage levels before connection
3. **Emergency stop**: Keep manual laser shutdown accessible
4. **Testing**: Test with low laser power initially
5. **Monitoring**: Watch first acquisition cycle carefully

## License

This code is provided as-is for research and educational purposes.

## Author

Generated with Claude Code
Date: 2025-10-29

## Support

For NI DAQmx Python API documentation:
- https://nidaqmx-python.readthedocs.io/

For hardware issues:
- Consult device manuals (camera, laser, SLM)
- Contact National Instruments support for DAQ issues

## Version History

- **v1.0** (2025-10-29): Initial implementation
  - Hardware-timed synchronization
  - 9-frame SIM pattern support
  - Microsecond precision timing
  - Camera ready monitoring
