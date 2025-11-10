+------------+-----------------------------------------------------------+
| **信息**   | 适用于Python的NI-DAQmx API                                |
+------------+-----------------------------------------------------------+
| **作者**   | National Instruments (美国国家仪器)                       |
+------------+-----------------------------------------------------------+

.. contents:: 目录
   :depth: 1
   :backlinks: none

关于
=====

**nidaqmx** 包允许您使用Python在NI数据采集(DAQ)设备上开发仪器、采集和控制应用程序。
本包由NI创建并提供支持。

文档
-------------

您可以在 `Read the Docs <http://nidaqmx-python.readthedocs.io/en/stable>`_ 上找到
**nidaqmx** 包的最新API文档。

请参考 `NI-DAQmx用户手册 <https://www.ni.com/docs/en-US/bundle/ni-daqmx/>`_ 以了解
NI-DAQmx概述、关键概念和测量基础知识。NI-DAQmx帮助文档也会随完整版NI-DAQmx本地安装。
有关更多信息，请参考 `此知识库文章 <http://digital.ni.com/express.nsf/bycode/exagg4>`_。

实现方式
--------------

该包在Python中实现，使用 `ctypes <https://docs.python.org/3/library/ctypes.html>`_
Python库作为NI-DAQmx C API的面向对象包装器。

支持的NI-DAQmx驱动程序版本
----------------------------------

**nidaqmx** 支持所有版本的NI-DAQmx。**nidaqmx** 包中的某些功能可能在早期版本的
NI-DAQmx驱动程序中不可用。有关如何安装最新版本NI-DAQmx驱动程序的详细信息，
请参考安装部分。

操作系统支持
------------------------

**nidaqmx** 支持NI-DAQmx驱动程序支持的Windows和Linux操作系统。请参考
`NI硬件和操作系统兼容性 <https://www.ni.com/r/hw-support>`_ 以了解哪些驱动程序
版本在给定操作系统上支持您的硬件。

Python版本支持
----------------------

**nidaqmx** 支持CPython 3.9及以上版本。

**nidaqmx** 支持PyPy3用于非gRPC用例。有关gRPC的PyPy支持状态，
请参见 `PyPy支持 (grpc/grpc#4221) <https://github.com/grpc/grpc/issues/4221>`_。

安装
============

您可以使用 `pip <http://pypi.python.org/pypi/pip>`_ 从
`PyPI <https://pypi.org/project/nidaqmx/>`_ 下载并安装 **nidaqmx**::

  $ python -m pip install nidaqmx

自动驱动程序安装
-----------------------------

运行 **nidaqmx** 需要安装NI-DAQmx。**nidaqmx** 模块附带了一个命令行界面(CLI)
来简化安装体验。您可以使用以下命令安装NI-DAQmx驱动程序::

  $ python -m nidaqmx installdriver

在Windows上，此命令将从ni.com下载并启动在线流式安装程序。在Linux上，
这将下载适用于您的Linux发行版的存储库注册包，并使用您的包管理器安装驱动程序。

手动驱动程序安装
--------------------------

访问 `ni.com/downloads <http://www.ni.com/downloads/>`_ 下载最新版本的NI-DAQmx。
推荐的 **附加项** 都不是 **nidaqmx** 功能所必需的，可以删除以减小安装大小。
建议您继续安装 **NI证书** 包，以允许您的操作系统信任NI构建的二进制文件，
从而改善您的软件和硬件安装体验。

入门
===============
为了使用 **nidaqmx** 包，您必须在系统上至少安装一个DAQ
(`数据采集 <https://www.ni.com/en/shop/data-acquisition.html>`_) 设备。
支持物理和模拟设备。以下示例使用X系列DAQ设备（例如：PXIe-6363、PCIe-6363或
USB-6363）。您可以使用 **NI MAX** 或 **NI硬件配置实用程序** 来验证和配置您的设备。

在 **NI MAX** 中查找和配置设备名称：

.. image:: https://raw.githubusercontent.com/ni/nidaqmx-python/ca9b8554e351a45172a3490a4716a52d8af6e95e/max_device_name.png
  :alt: NI MAX设备名称
  :align: center
  :width: 800px

在 **NI硬件配置实用程序** 中查找和配置设备名称：

.. image:: https://raw.githubusercontent.com/ni/nidaqmx-python/ca9b8554e351a45172a3490a4716a52d8af6e95e/hwcu_device_name.png
  :alt: NI HWCU设备名称
  :align: center
  :width: 800px

Python示例
===============

您可以在GitHub存储库的 `nidaqmx-python示例 <https://github.com/ni/nidaqmx-python/tree/master/examples>`_
目录中找到各种示例。为获得最佳效果，请使用与您正在使用的 **nidaqmx** 版本对应的示例。
例如，如果您使用的是1.0.0版本，请查看
`1.0.0标签中的示例目录 <https://github.com/ni/nidaqmx-python/tree/1.0.0/examples>`_。
较新的示例可能演示旧版本 **nidaqmx** 中不可用的功能。

NI-DAQmx中的关键概念
=========================

任务
-----
任务是一个或多个虚拟通道的集合，具有时序、触发和其他属性。
有关更多信息，请参考 `NI-DAQmx任务 <https://www.ni.com/docs/en-US/bundle/ni-daqmx/page/tasksnidaqmx.html>`_。

创建任务的示例代码：

.. code-block:: python

  >>> import nidaqmx
  >>> with nidaqmx.Task() as task:
  ...     pass

虚拟通道
----------------
虚拟通道，有时泛称为通道，是封装物理通道以及其他特定于通道的信息（例如：范围、
端子配置和自定义缩放）的软件实体，用于格式化数据。物理通道是可以测量或生成模拟或
数字信号的端子或引脚。单个物理通道可以包含多个端子，如差分模拟输入通道或八线数字
端口的情况。设备上的每个物理通道都有一个唯一的名称（例如cDAQ1Mod4/ai0、Dev2/ao5和
Dev6/ctr3），遵循NI-DAQmx物理通道命名约定。
有关更多信息，请参考 `NI-DAQmx通道 <https://www.ni.com/docs/en-US/bundle/ni-daqmx/page/chans.html>`_。

将模拟输入通道添加到任务、配置范围并读取数据的示例代码：

.. code-block:: python

  >>> import nidaqmx
  >>> with nidaqmx.Task() as task:
  ...     task.ai_channels.add_ai_voltage_chan("Dev1/ai0", min_val=-10.0, max_val=10.0)
  ...     task.read()
  ...
  AIChannel(name=Dev1/ai0)
  -0.14954069643238624

将多个模拟输入通道添加到任务、配置它们的范围并读取数据的示例代码：

.. code-block:: python

  >>> import nidaqmx
  >>> with nidaqmx.Task() as task:
  ...     task.ai_channels.add_ai_voltage_chan("Dev1/ai0", min_val=-5.0, max_val=5.0)
  ...     task.ai_channels.add_ai_voltage_chan("Dev1/ai1", min_val=-10.0, max_val=10.0)
  ...     task.read()
  ...
  AIChannel(name=Dev1/ai0)
  AIChannel(name=Dev1/ai1)
  [-0.07477034821619312, 0.8642841883602405]

时序
------
您可以使用软件时序或硬件时序来控制何时采集或生成信号。使用硬件时序时，
数字信号（例如设备上的时钟）控制采集或生成的速率。使用软件时序时，
采样的采集或生成速率由软件和操作系统决定，而不是由测量设备决定。
硬件时钟的运行速度可以远远快于软件循环。硬件时钟也比软件循环更准确。
有关更多信息，请参考 `时序，硬件与软件 <https://www.ni.com/docs/en-US/bundle/ni-daqmx/page/hardwresoftwretiming.html>`_。

使用硬件时序采集有限量数据的示例代码：

.. code-block:: python

  >>> import nidaqmx
  >>> from nidaqmx.constants import AcquisitionType, READ_ALL_AVAILABLE
  >>> with nidaqmx.Task() as task:
  ...     task.ai_channels.add_ai_voltage_chan("Dev1/ai0")
  ...     task.timing.cfg_samp_clk_timing(1000.0, sample_mode=AcquisitionType.FINITE, samps_per_chan=10)
  ...     data = task.read(READ_ALL_AVAILABLE)
  ...     print("采集的数据: [" + ", ".join(f"{value:f}" for value in data) + "]")
  ...
  AIChannel(name=Dev1/ai0)
  采集的数据: [-0.149693, 2.869503, 4.520249, 4.704886, 2.875912, -0.006104, -2.895596, -4.493698, -4.515671, -2.776574]

TDMS日志记录
------------
技术数据管理流(TDMS)是一种允许高速数据记录的二进制文件格式。
当您启用TDMS数据记录时，NI-DAQmx可以将数据直接从设备缓冲区流式传输到硬盘。
有关更多信息，请参考 `TDMS日志记录 <https://www.ni.com/docs/en-US/bundle/ni-daqmx/page/datalogging.html>`_。

采集有限量数据并将其记录到TDMS文件的示例代码：

.. code-block:: python

  >>> import nidaqmx
  >>> from nidaqmx.constants import AcquisitionType, LoggingMode, LoggingOperation, READ_ALL_AVAILABLE
  >>> with nidaqmx.Task() as task:
  ...     task.ai_channels.add_ai_voltage_chan("Dev1/ai0")
  ...     task.timing.cfg_samp_clk_timing(1000.0, sample_mode=AcquisitionType.FINITE, samps_per_chan=10)
  ...     task.in_stream.configure_logging("TestData.tdms", LoggingMode.LOG_AND_READ, operation=LoggingOperation.CREATE_OR_REPLACE)
  ...     data = task.read(READ_ALL_AVAILABLE)
  ...     print("采集的数据: [" + ", ".join(f"{value:f}" for value in data) + "]")
  ...
  AIChannel(name=Dev1/ai0)
  采集的数据: [-0.149693, 2.869503, 4.520249, 4.704886, 2.875912, -0.006104, -2.895596, -4.493698, -4.515671, -2.776574]

要读取TDMS文件，您可以使用 **npTDMS** 第三方模块。
有关详细用法，请参考 `npTDMS <https://pypi.org/project/npTDMS/>`_。

读取上述示例创建的TDMS文件并显示数据的示例代码：

.. code-block:: python

  >>> from nptdms import TdmsFile
  >>> with TdmsFile.read("TestData.tdms") as tdms_file:
  ...   for group in tdms_file.groups():
  ...     for channel in group.channels():
  ...       data = channel[:]
  ...       print("数据: [" + ", ".join(f"{value:f}" for value in data) + "]")
  ...
  数据: [-0.149693, 2.869503, 4.520249, 4.704886, 2.875912, -0.006104, -2.895596, -4.493698, -4.515671, -2.776574]

绘制数据
---------
要将采集的数据可视化为波形，您可以使用 **matplotlib.pyplot** 第三方模块。
有关详细用法，请参考 `Pyplot教程 <https://matplotlib.org/stable/tutorials/pyplot.html#sphx-glr-tutorials-pyplot-py>`_。

使用 **matplotlib.pyplot** 模块为采集的数据绘制波形的示例代码：

.. code-block:: python

  >>> import nidaqmx
  >>> from nidaqmx.constants import AcquisitionType, READ_ALL_AVAILABLE
  >>> import matplotlib.pyplot as plt
  >>> with nidaqmx.Task() as task:
  ...   task.ai_channels.add_ai_voltage_chan("Dev1/ai0")
  ...   task.timing.cfg_samp_clk_timing(1000.0, sample_mode=AcquisitionType.FINITE, samps_per_chan=50)
  ...   data = task.read(READ_ALL_AVAILABLE)
  ...   plt.plot(data)
  ...   plt.ylabel('幅度')
  ...   plt.title('波形')
  ...   plt.show()
  ...
  AIChannel(name=Dev1/ai0)
  [<matplotlib.lines.Line2D object at 0x00000141D7043970>]
  Text(0, 0.5, '幅度')
  Text(0.5, 1.0, '波形')

.. image:: https://raw.githubusercontent.com/ni/nidaqmx-python/ca9b8554e351a45172a3490a4716a52d8af6e95e/waveform.png
  :alt: 波形
  :align: center
  :width: 400px

有关如何使用 **nidaqmx** 包的更多信息，请参考下面的 **使用方法** 部分。

.. _usage-section:

使用方法
=====
以下是使用 **nidaqmx.task.Task** 对象的基本示例。此示例说明了单个动态
**nidaqmx.task.Task.read** 方法如何返回适当的数据类型。

.. code-block:: python

  >>> import nidaqmx
  >>> with nidaqmx.Task() as task:
  ...     task.ai_channels.add_ai_voltage_chan("Dev1/ai0")
  ...     task.read()
  ...
  -0.07476920729381246
  >>> with nidaqmx.Task() as task:
  ...     task.ai_channels.add_ai_voltage_chan("Dev1/ai0")
  ...     task.read(number_of_samples_per_channel=2)
  ...
  [0.26001373311970705, 0.37796597238117036]
  >>> from nidaqmx.constants import LineGrouping
  >>> with nidaqmx.Task() as task:
  ...     task.di_channels.add_di_chan(
  ...         "cDAQ2Mod4/port0/line0:1", line_grouping=LineGrouping.CHAN_PER_LINE)
  ...     task.read(number_of_samples_per_channel=2)
  ...
  [[False, True], [True, True]]

还存在一个单一的动态 **nidaqmx.task.Task.write** 方法。

.. code-block:: python

  >>> import nidaqmx
  >>> from nidaqmx.types import CtrTime
  >>> with nidaqmx.Task() as task:
  ...     task.co_channels.add_co_pulse_chan_time("Dev1/ctr0")
  ...     sample = CtrTime(high_time=0.001, low_time=0.001)
  ...     task.write(sample)
  ...
  1
  >>> with nidaqmx.Task() as task:
  ...     task.ao_channels.add_ao_voltage_chan("Dev1/ao0")
  ...     task.write([1.1, 2.2, 3.3, 4.4, 5.5], auto_start=True)
  ...
  5

考虑使用 **nidaqmx.stream_readers** 和 **nidaqmx.stream_writers** 类来提高应用程序的
性能，这些类接受预先分配的NumPy数组。

以下是使用 **nidaqmx.system.System** 对象的示例。

.. code-block:: python

  >>> import nidaqmx.system
  >>> system = nidaqmx.system.System.local()
  >>> system.driver_version
  DriverVersion(major_version=16L, minor_version=0L, update_version=0L)
  >>> for device in system.devices:
  ...     print(device)
  ...
  Device(name=Dev1)
  Device(name=Dev2)
  Device(name=cDAQ1)
  >>> import collections
  >>> isinstance(system.devices, collections.Sequence)
  True
  >>> device = system.devices['Dev1']
  >>> device == nidaqmx.system.Device('Dev1')
  True
  >>> isinstance(device.ai_physical_chans, collections.Sequence)
  True
  >>> phys_chan = device.ai_physical_chans['ai0']
  >>> phys_chan
  PhysicalChannel(name=Dev1/ai0)
  >>> phys_chan == nidaqmx.system.PhysicalChannel('Dev1/ai0')
  True
  >>> phys_chan.ai_term_cfgs
  [<TerminalConfiguration.RSE: 10083>, <TerminalConfiguration.NRSE: 10078>, <TerminalConfiguration.DIFFERENTIAL: 10106>]
  >>> from enum import Enum
  >>> isinstance(phys_chan.ai_term_cfgs[0], Enum)
  True

Bug报告 / 功能请求
=======================

要报告错误或提交功能请求，请使用
`GitHub问题页面 <https://github.com/ni/nidaqmx-python/issues>`_。

寻求帮助时需要包含的信息
-------------------------------------------

在打开问题时，请包含 **所有** 以下信息：

- 有关如何重现问题的详细步骤和完整的回溯信息（如果适用）。
- 使用的Python版本::

  $ python -c "import sys; print(sys.version)"

- 使用的 **nidaqmx** 和numpy包的版本::

  $ python -m pip list

- 使用的NI-DAQmx驱动程序版本。按照
  `此知识库文章 <http://digital.ni.com/express.nsf/bycode/ex8amn>`_
  确定您安装的NI-DAQmx版本。
- 操作系统和版本，例如Windows 7、CentOS 7.2等。

许可证
=======

**nidaqmx** 采用MIT风格的许可证（请参见
`LICENSE <https://github.com/ni/nidaqmx-python/blob/master/LICENSE>`_）。
其他合并的项目可能采用不同的许可证。所有许可证都允许非商业和商业使用。
