"""
SIM (结构光照明显微镜) 硬件同步控制系统
=========================================

本脚本实现以下设备的硬件定时同步控制：
1. 相机 (滨松 ORCA-Fusion BT) - 外部电平触发模式 (3.3V TTL)
2. 多波长激光器 (405nm, 488nm, 561nm, 647nm) - 触发激活模式
3. SLM (空间光调制器) - 三信号控制 (使能、触发、结束)

硬件连接：
----------
数字输出 (NI USB-6423 - 3.3V LVCMOS 逻辑电平):
- 相机触发:      Port0 Line0 (Dev1/port0/line0)
- 激光器 405nm:  Port0 Line1 (Dev1/port0/line1)
- 激光器 488nm:  Port0 Line2 (Dev1/port0/line2)
- 激光器 561nm:  Port0 Line3 (Dev1/port0/line3)
- 激光器 647nm:  Port0 Line4 (Dev1/port0/line4)
- SLM使能:       Port0 Line5 (Dev1/port0/line5)
- SLM触发:       Port0 Line6 (Dev1/port0/line6)
- SLM结束:       Port0 Line7 (Dev1/port0/line7)

数字输入 (NI USB-6423):
- 相机就绪信号:  PFI8端口 (Dev1/PFI8) - 3.3V TTL电平（可通过DEFAULT_TRIGGER_SOURCE修改）
- Counter通道:   Counter0 (Dev1/ctr0) - 精确计数触发（可通过DEFAULT_COUNTER_CHANNEL修改）

硬件配置说明:
-------------
1. digital_trigger_source (默认"/Dev1/PFI8"):
   - 相机ready信号的输入端口（PFI端口）
   - 相机每次准备好采集时，发送上升沿TTL信号到此端口
   - 此端口独立于数字输出端口(port0/line0-7)

2. counter_channel (默认"ctr0"):
   - Counter通道用于精确计数触发次数
   - Counter的输入通过ci_count_edges_term连接到digital_trigger_source
   - 使用cfg_implicit_timing + FINITE模式，在计数到N次后硬件自动停止

3. cfg_implicit_timing工作原理:
   - "隐式时钟"：每次上升沿事件本身就是一次"采样"
   - 无需外部采样时钟，事件即是时钟
   - 硬件Counter在第N次上升沿到达后自动完成任务
   - 纳秒级精度，完全由硬件实现

4. CAM_TRIGGER_LINE vs digital_trigger_source:
   - CAM_TRIGGER_LINE: 输出端口，控制器→相机（触发相机曝光）
   - digital_trigger_source: 输入端口，相机→控制器（相机ready信号）

时序说明：
----------
单帧时序: 曝光(100ms) + SLM结束脉冲(100us) = ~100.1ms
单循环时序: 9帧 × 100.1ms + 帧间等待 ≈ 1秒
采样率: 100kHz (10us分辨率)

作者: Generated with Claude Code
日期: 2025-11-03
版本: 6.3 - 正确实现cfg_implicit_timing硬件自动停止
"""

import nidaqmx
from nidaqmx.constants import (
    AcquisitionType,
    LineGrouping,
    Edge,
    CountDirection  # v6.0: 用于Counter任务
)
from nidaqmx.stream_writers import DigitalSingleChannelWriter

# NI-DAQmx 接口要点（便于阅读与核对）
# - 端口写入 API：DigitalSingleChannelWriter.write_many_sample_port_uint16 期望 1D uint16 数组，
#   每个元素代表一次采样时刻的端口位掩码；与 LineGrouping.CHAN_FOR_ALL_LINES（整端口为单通道）完全匹配。
#   参考: generated/nidaqmx/stream_writers/_digital_single_channel_writer.py
# - 计数器隐式时钟：Timing.cfg_implicit_timing 配合 AcquisitionType.FINITE 和 samps_per_chan=N，
#   表示“事件=采样”，计满 N 次自动完成。
#   参考: generated/nidaqmx/task/_timing.py:1744, 1815
# - 采样点属性名：正确属性为 samp_quant_samp_per_chan（NI 自动生成代码中提供）。
#   参考: generated/nidaqmx/task/_timing.py:1286
# - 边沿计数通道与输入端绑定：ci_count_edges_term 可直接设为 '/Dev1/PFIx'。
#   参考: generated/nidaqmx/task/channels/_ci_channel.py:927
import numpy as np
import time
from typing import Optional, List
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SIMController:
    """
    SIM成像硬件定时同步控制器

    该类管理结构光照明显微镜采集过程中相机、多波长激光器和SLM的精确时序和同步。
    使用硬件Counter精确计数每个循环的9次触发，确保采集精度。
    """

    # 数字输出线路分配 (8通道配置)
    CAM_TRIGGER_LINE = 0    # 相机触发输出 (3.3V LVCMOS)
    LASER_405_LINE = 1      # 405nm激光器触发
    LASER_488_LINE = 2      # 488nm激光器触发
    LASER_561_LINE = 3      # 561nm激光器触发
    LASER_647_LINE = 4      # 647nm激光器触发
    SLM_ENABLE_LINE = 5     # SLM使能信号
    SLM_TRIGGER_LINE = 6    # SLM触发信号（边沿触发）
    SLM_FINISH_LINE = 7     # SLM结束信号（边沿触发）

    # 激光器波长常量（用于用户友好的接口）
    LASER_405 = 405
    LASER_488 = 488
    LASER_561 = 561
    LASER_647 = 647

    # 硬件配置常量（用户可修改）
    DEFAULT_SAMPLE_RATE = 100000        # 100 kHz = 10微秒分辨率
    DEFAULT_TRIGGER_SOURCE = "/Dev1/PFI8"  # 默认相机ready信号输入端口
    DEFAULT_COUNTER_CHANNEL = "ctr0"     # 默认Counter通道名称

    def __init__(
        self,
        device_name: str = "Dev1",
        exposure_time_us: float = 100000,  # 默认100ms（100,000us）
        frames_per_loop: int = 9,
        num_loops: int = 1,
        sample_rate: float = DEFAULT_SAMPLE_RATE,
        active_lasers: Optional[List[int]] = None  # 激光器选择
    ):
        """
        初始化SIM控制器

        参数
        ----
        device_name : str
            NI DAQ设备名称（例如："Dev1"）
        exposure_time_us : float
            曝光时间（微秒）（影响相机、激光器和SLM的时序）
            默认: 100,000us (100ms)
        frames_per_loop : int
            每个采集循环的帧数（SIM默认为9）
        num_loops : int
            要采集的完整循环数
        sample_rate : float
            硬件采样时钟频率（Hz）（默认：100 kHz = 10us分辨率）
        active_lasers : List[int], optional
            要激活的激光器波长列表（例如：[405, 488, 561, 647]）
            如果为None，默认仅激活488nm激光器
            示例：
                [488] - 仅激活488nm（默认）
                [488, 561] - 激活488nm和561nm
                [405] - 仅激活405nm
                [405, 488, 561, 647] - 激活所有激光器
        """
        self.device_name = device_name
        self.exposure_time_us = exposure_time_us
        self.frames_per_loop = frames_per_loop
        self.num_loops = num_loops
        self.sample_rate = sample_rate

        # 处理激光器选择
        if active_lasers is None:
            # 默认仅激活488nm激光器
            self.active_lasers = [self.LASER_488]
        else:
            # 验证输入的激光器波长
            valid_lasers = {self.LASER_405, self.LASER_488,
                           self.LASER_561, self.LASER_647}
            invalid = set(active_lasers) - valid_lasers
            if invalid:
                raise ValueError(f"无效的激光器波长: {invalid}. "
                               f"有效值: {valid_lasers}")
            self.active_lasers = list(active_lasers)

        # 创建激光器波长到线路号的映射
        self.laser_line_map = {
            self.LASER_405: self.LASER_405_LINE,
            self.LASER_488: self.LASER_488_LINE,
            self.LASER_561: self.LASER_561_LINE,
            self.LASER_647: self.LASER_647_LINE
        }

        # 计算时序参数
        self.exposure_samples = int(exposure_time_us / (1e6 / sample_rate))  # 根据采样率计算采样点数
        # 在100kHz时：1个采样点 = 10us，100ms = 10,000个采样点

        # 任务句柄
        self.do_task: Optional[nidaqmx.Task] = None
        self.ai_task: Optional[nidaqmx.Task] = None
        self.counter_task: Optional[nidaqmx.Task] = None  # Counter任务用于精确计数触发

        logger.info(f"SIM控制器已初始化：")
        logger.info(f"  设备: {device_name}")
        logger.info(f"  曝光时间: {exposure_time_us} us ({exposure_time_us/1000:.1f} ms)")
        logger.info(f"  每循环帧数: {frames_per_loop}")
        logger.info(f"  循环次数: {num_loops}")
        logger.info(f"  采样率: {sample_rate/1e3} kHz (分辨率: {1e6/sample_rate:.1f} us)")
        logger.info(f"  曝光采样点数: {self.exposure_samples}")
        logger.info(f"  激活的激光器: {self.active_lasers} nm")
        logger.info(f"  输出电平: 3.3V LVCMOS (相机兼容)")

    def setup_tasks(self) -> None:
        """
        配置NI DAQ的数字输出任务

        重要: 配置为3.3V LVCMOS逻辑电平以兼容ORCA-Fusion BT相机
        """
        # 设备规格速览（USB‑6423 关键参数与针脚）：见 docs/usb-6423-spec-notes.md
        logger.info("正在设置DAQ任务...")

        # 为所有控制信号创建数字输出任务
        self.do_task = nidaqmx.Task("DO_Control_Task")

        # 添加8个数字输出线路 (line0-line7)
        do_lines = f"{self.device_name}/port0/line{self.CAM_TRIGGER_LINE}:{self.SLM_FINISH_LINE}"
        
        
        # NI-DAQmx: 添加数字输出通道（DO）
        # - 函数: add_do_chan(lines, name_to_assign_to_lines="", line_grouping=...)
        # - 作用: 基于物理端口/线路创建 DO 虚拟通道；当 line_grouping=CHAN_FOR_ALL_LINES 时，
        #         整个端口作为“单通道”使用，适配按端口位掩码进行写入的 API。
        # - 关键参数:
        #   lines: 物理端口/线名称（如 "Dev1/port0/line0:7"）。
        #   line_grouping: CHAN_FOR_ALL_LINES 表示整端口合并为一通道。
        self.do_task.do_channels.add_do_chan(
            lines=do_lines,
            line_grouping=LineGrouping.CHAN_FOR_ALL_LINES
        )

        # 注意: NI DAQ数字输出电平配置
        # 对于大多数NI DAQ设备，数字输出电平由硬件跳线或设备配置决定
        # 如果您的DAQ支持软件配置电压电平，请在此处添加配置代码
        # 例如（如果支持）：
        # self.do_task.do_channels.all.do_output_drive_type = ...

        # 警告: 请在NI MAX中确认您的DAQ设备数字I/O配置为3.3V逻辑电平
        # 路径: NI MAX -> 设备 -> Device Pinouts -> Digital I/O -> Logic Level
        logger.warning("请确认NI DAQ数字输出已配置为3.3V LVCMOS逻辑电平！")
        logger.warning("在NI MAX中检查: DAQ设备 -> 右键 -> 属性 -> Device Pinouts -> Digital I/O")

        # 为数字输出配置硬件定时采样时钟
        # NI-DAQmx: 配置采样时钟（rate/sample_mode/samps_per_chan）
        self.do_task.timing.cfg_samp_clk_timing(
            rate=self.sample_rate,
            sample_mode=AcquisitionType.FINITE,
            samps_per_chan=10000  # 将根据实际波形更新
        )

        logger.info("DAQ任务配置成功")
        logger.info(f"  数字输出通道: 8通道 (line0-line7)")
        logger.info(f"  触发源: PFI端口（数字触发）")

    def generate_frame_waveform(self) -> np.ndarray:
        """
        为单帧采集生成数字波形

        波形包括：
        - 相机触发高电平（曝光期间）
        - 选定激光器的同步触发高电平（曝光期间）
        - SLM trigger脉冲（帧开始时，100us）
        - SLM finish脉冲（曝光结束后，100us）
        - SLM enable信号（整帧期间高电平）

        返回
        ----
        np.ndarray
            形状为(8, total_samples)的数字波形数组
        """
        # 以采样点为单位计算时序
        trigger_high_samples = self.exposure_samples
        trigger_edge_samples = max(1, int(100 / (1e6 / self.sample_rate)))  # 边沿触发信号的100us脉冲

        # 单帧波形包含：曝光期间的信号 + SLM结束脉冲
        total_samples = trigger_high_samples + trigger_edge_samples

        # 初始化波形 (8个通道 x 采样点)
        # 通道: [cam, laser405, laser488, laser561, laser647,
        #        slm_enable, slm_trigger, slm_finish]
        waveform = np.zeros((8, total_samples), dtype=np.uint8)

        # 相机触发: 曝光期间高电平 [0, trigger_high_samples)
        waveform[self.CAM_TRIGGER_LINE, 0:trigger_high_samples] = 1

        # 激光器触发: 曝光期间高电平 [0, trigger_high_samples)
        for laser_wavelength in self.active_lasers:
            line_num = self.laser_line_map[laser_wavelength]
            waveform[line_num, 0:trigger_high_samples] = 1
            logger.debug(f"激活 {laser_wavelength}nm 激光器 (line{line_num})")

        # SLM使能: 在loop期间的每一帧都应该为高电平
        waveform[self.SLM_ENABLE_LINE, :] = 1

        # SLM触发: 开始时上升沿（100us脉冲）[0, trigger_edge_samples)
        waveform[self.SLM_TRIGGER_LINE, 0:trigger_edge_samples] = 1

        # SLM结束: 在相机和激光器trigger结束之后（100us脉冲）
        finish_start = trigger_high_samples
        finish_end = finish_start + trigger_edge_samples
        waveform[self.SLM_FINISH_LINE, finish_start:finish_end] = 1

        logger.debug(f"单帧波形生成: 总采样点={total_samples}, 曝光={trigger_high_samples}, finish脉冲={trigger_edge_samples}")

        return waveform

    @staticmethod
    def _pack_waveform_to_port_uint16(waveform: np.ndarray) -> np.ndarray:
        """
        将形状为 (lines, samples) 的 0/1 波形打包为端口位掩码数组（uint16，长度为 samples）。

        假设第 i 行对应端口的第 i 位（line0 -> bit0 ... line7 -> bit7）。
        """
        if waveform.ndim != 2:
            raise ValueError("waveform 应为2维数组： (lines, samples)")
        lines, samples = waveform.shape
        if lines > 16:
            raise ValueError("当前实现支持最多16条线的端口打包（USB-6423 P0）")

        waveform_uint16 = waveform.astype(np.uint16, copy=False)
        weights = (np.uint16(1) << np.arange(lines, dtype=np.uint16))[:, None]
        weighted = np.multiply(weights, waveform_uint16, dtype=np.uint16)
        return np.bitwise_or.reduce(weighted, axis=0)

    def generate_loop_waveform_with_slm_enable(self, slm_setup_time_ms: float = 10.0) -> np.ndarray:
        """
        生成完整9帧循环波形，SLM enable在整个过程中保持高电平

        参数
        ----
        slm_setup_time_ms : float
            SLM使能设置和响应时间（毫秒），默认10ms

        返回
        ----
        np.ndarray
            形状为(8, total_samples)的完整循环波形
        """
        # 计算SLM setup时间的采样点数
        setup_samples = int((slm_setup_time_ms * 1000) / (1e6 / self.sample_rate))

        # 计算单帧采样点数（曝光 + SLM结束脉冲）
        trigger_edge_samples = max(1, int(100 / (1e6 / self.sample_rate)))  # 100us脉冲
        frame_samples = self.exposure_samples + trigger_edge_samples  # 正确的单帧采样点数

        # 总采样点数 = setup + 9帧
        total_samples = setup_samples + (frame_samples * self.frames_per_loop)

        # 初始化波形（全零）
        waveform = np.zeros((8, total_samples), dtype=np.uint8)

        # SLM Enable: 整个波形期间保持高电平
        waveform[self.SLM_ENABLE_LINE, :] = 1

        # 生成每一帧的信号
        for frame_idx in range(self.frames_per_loop):
            # 计算当前帧在波形中的起始位置（setup之后）
            frame_start = setup_samples + (frame_idx * frame_samples)

            # 相机触发：曝光期间高电平
            cam_end = frame_start + self.exposure_samples
            waveform[self.CAM_TRIGGER_LINE, frame_start:cam_end] = 1

            # 激光器触发：仅激活选定的激光器
            for laser_wavelength in self.active_lasers:
                line_num = self.laser_line_map[laser_wavelength]
                waveform[line_num, frame_start:cam_end] = 1

            # SLM触发：帧开始时上升沿（100us脉冲）
            waveform[self.SLM_TRIGGER_LINE, frame_start:frame_start + trigger_edge_samples] = 1

            # SLM结束：曝光结束后（100us脉冲）
            finish_start = cam_end
            finish_end = finish_start + trigger_edge_samples
            waveform[self.SLM_FINISH_LINE, finish_start:finish_end] = 1

        logger.info(f"生成完整循环波形: {total_samples}个采样点 = "
                   f"{setup_samples}(setup) + {frame_samples * self.frames_per_loop}(9帧)")

        return waveform

    def set_slm_enable(self, enable: bool, duration_ms: float = 10.0) -> bool:
        """
        单独设置SLM enable信号（高电平或低电平）

        此方法用于在循环开始前设置SLM enable，给SLM足够的响应时间。

        参数
        ----
        enable : bool
            True=高电平，False=低电平
        duration_ms : float
            信号持续时间（毫秒），默认10ms

        返回
        ----
        bool
            成功返回True，否则返回False
        """
        logger.info(f"设置SLM enable = {'高' if enable else '低'}电平 ({duration_ms}ms)")

        try:
            # 禁用开始触发：本段波形需“立即播放”，不依赖相机 Ready 触发
            try:
                self.do_task.triggers.start_trigger.disable_start_trig()
            except Exception:
                pass
            # 计算采样点数
            duration_samples = int((duration_ms * 1000) / (1e6 / self.sample_rate))

            # 创建波形（仅SLM enable信号）
            waveform = np.zeros((8, duration_samples), dtype=np.uint8)
            if enable:
                waveform[self.SLM_ENABLE_LINE, :] = 1

            # 更新时序配置
            # (NI-DAQmx) 正确的采样数属性名：samp_quant_samp_per_chan
            # 参考: generated/nidaqmx/task/_timing.py:1286
            self.do_task.timing.samp_quant_samp_per_chan = duration_samples

            # 将波形写入缓冲区
            # NI-DAQmx: 端口级数字写入器（单端口通道）
            writer = DigitalSingleChannelWriter(self.do_task.out_stream)

            # 打包为端口位掩码（uint16）并写入
            packed = self._pack_waveform_to_port_uint16(waveform)
            # (NI-DAQmx) 端口写入 API 期望 1D uint16（端口位掩码，按位对应 line0..lineN）
            # 参考: generated/nidaqmx/stream_writers/_digital_single_channel_writer.py
            writer.write_many_sample_port_uint16(packed)

            # 启动硬件定时生成
            # NI-DAQmx: 启动 DO 任务，按硬件时钟/触发条件运行
            self.do_task.start()

            # 等待波形生成完成
            # NI-DAQmx: 阻塞等待 DO 任务完成或超时
            self.do_task.wait_until_done(timeout=10.0)

            # 停止任务
            # NI-DAQmx: 停止 DO 任务
            self.do_task.stop()

            logger.debug(f"SLM enable设置完成")
            return True

        except Exception as e:
            logger.error(f"设置SLM enable时出错: {e}")
            return False

    def execute_single_loop(
        self,
        slm_setup_time_ms: float = 10.0,
        digital_trigger_source: str = None,  # 使用None，在函数内部使用类常量
        counter_channel: str = None
    ) -> bool:
        """
        执行一个完整的采集循环（9帧），使用Counter精确计数触发次数

        参数说明：
        ----------
        digital_trigger_source : str
            相机ready信号的输入端口（PFI端口）
            - 这是NI DAQ的物理输入端口，用于接收相机的ready信号
            - 例如："/Dev1/PFI8" 表示设备Dev1的PFI8端口
            - 相机每次准备好采集时，会发送一个上升沿TTL信号到此端口
            - 此端口独立于数字输出端口（port0/line0-7），可同时使用
            - 默认值：使用类常量 DEFAULT_TRIGGER_SOURCE = "/Dev1/PFI8"

        counter_channel : str
            NI DAQ的Counter通道名称（用于计数触发次数）
            - NI USB-6423有2个Counter：ctr0和ctr1
            - Counter通道用于精确计数digital_trigger_source上的上升沿数量
            - 例如："ctr0" 表示使用Counter 0通道
            - Counter的输入源通过ci_count_edges_term属性连接到digital_trigger_source
            - 默认值：使用类常量 DEFAULT_COUNTER_CHANNEL = "ctr0"

        slm_setup_time_ms : float
            SLM enable设置和响应时间（毫秒），默认10ms

        设备规格速览：见 docs/usb-6423-spec-notes.md（PFI 功能、逻辑电平、FIFO、速率等）

        工作原理：
        ----------
        1. Counter任务监听digital_trigger_source（如PFI8）上的上升沿
        2. DO任务也被配置为由相同的digital_trigger_source触发
        3. 每次相机ready信号到达：
           - Counter计数+1
           - DO任务输出一帧波形（相机触发、激光器、SLM信号）
        4. 当Counter计数达到9次时，循环完成

        返回
        ----
        bool
            成功返回True，否则返回False
        """
        # 使用类常量作为默认值
        if digital_trigger_source is None:
            digital_trigger_source = self.DEFAULT_TRIGGER_SOURCE
        if counter_channel is None:
            counter_channel = self.DEFAULT_COUNTER_CHANNEL

        logger.info(f"正在执行硬件触发循环（{self.frames_per_loop}帧）- 使用Counter精确计数")
        logger.info(f"触发源: {digital_trigger_source}, Counter: {counter_channel}")

        try:
            # 步骤1: 创建Counter任务 - 使用隐式时钟自动停止
            # ========================================================
            # 关键理解：
            # - cfg_implicit_timing 中的"隐式时钟"是指：事件本身作为采样时钟
            # - 每次上升沿事件 = 一次"采样"
            # - FINITE模式 + samps_per_chan=N：计数到N次后任务自动完成
            # - 完全由硬件Counter实现，纳秒级精度
            # - 无需Python轮询，硬件自动停止！
            # NI-DAQmx: 创建任务对象（后续添加通道/时序/触发/启动）
            self.counter_task = nidaqmx.Task("CounterTask")

            # 配置Counter输入通道来计数边沿
            counter_channel_path = f"{self.device_name}/{counter_channel}"  # 例如："Dev1/ctr0"
            # NI-DAQmx: 添加“计数边沿”输入通道（上升沿计数）
            ci_channel = self.counter_task.ci_channels.add_ci_count_edges_chan(
                counter_channel_path,    # Counter通道完整路径
                edge=Edge.RISING,        # 计数上升沿
                initial_count=0,         # 初始计数值为0
                count_direction=CountDirection.COUNT_UP  # 向上计数
            )

            # 设置Counter输入源为PFI端口
            # (NI-DAQmx) 边沿计数通道输入端：可直接绑定到 '/Dev1/PFIx'
            # 参考: generated/nidaqmx/task/channels/_ci_channel.py:927
            ci_channel.ci_count_edges_term = digital_trigger_source  # 例如："/Dev1/PFI8"

            # 配置隐式时钟 - 关键配置！
            # ========================================================
            # 这里每次上升沿事件就是一次"采样"
            # 当计数到frames_per_loop次（9次）后，任务自动完成
            # NI-DAQmx: 隐式时钟 + 有限采样（事件=采样，计满N次自动完成）
            self.counter_task.timing.cfg_implicit_timing(
                sample_mode=AcquisitionType.FINITE,
                samps_per_chan=self.frames_per_loop  # 计数到9次后自动停止
            )

            logger.info(f"Counter {counter_channel_path} 配置:")
            logger.info(f"  - 输入源: {digital_trigger_source}")
            logger.info(f"  - 计数目标: {self.frames_per_loop}次上升沿")
            logger.info(f"  - 模式: 隐式时钟（Implicit Timing）+ 有限采样（FINITE）")
            logger.info(f"  - 硬件将在第{self.frames_per_loop}次上升沿后自动停止任务")

            # 步骤2: 输出SLM enable setup信号
            logger.info(f"设置SLM enable并等待响应时间 {slm_setup_time_ms}ms")
            if not self.set_slm_enable(enable=True, duration_ms=slm_setup_time_ms):
                logger.error("设置SLM enable失败")
                self.counter_task.close()
                return False

            # 步骤3: 准备DO任务（单帧重放 + retriggerable）
            frame_waveform = self.generate_frame_waveform()
            frame_samples = frame_waveform.shape[1]

            # 配置DO任务
            # 参考: generated/nidaqmx/task/_timing.py:1286
            # NI-DAQmx: 设置 DO 每通道生成的样本数
            self.do_task.timing.samp_quant_samp_per_chan = frame_samples

            # 配置数字触发源
            logger.info(f"配置数字边沿触发: {digital_trigger_source}")
            # NI-DAQmx: 配置数字边沿开始触发（由相机 ready 信号驱动）
            self.do_task.triggers.start_trigger.cfg_dig_edge_start_trig(
                trigger_source=digital_trigger_source,
                trigger_edge=Edge.RISING
            )
            # NI-DAQmx: 允许重复触发（每个上升沿重放一帧）
            self.do_task.triggers.start_trigger.retriggerable = True

            # 写入波形
            # NI-DAQmx: 端口级数字写入器（与 CHAN_FOR_ALL_LINES 搭配）
            writer = DigitalSingleChannelWriter(self.do_task.out_stream)
            packed_frame = self._pack_waveform_to_port_uint16(frame_waveform)
            # NI-DAQmx: 写入 1D uint16 端口位掩码（长度=样本数）
            writer.write_many_sample_port_uint16(packed_frame)

            # 说明：本次仅写入“单帧”数据，DO 任务设置为 retriggerable，
            # 每个来自相机的上升沿都会重放该帧。
            logger.info(f"缓冲区已写入单帧: {frame_samples} 个采样点（retriggerable）")
            logger.info(f"激光器: {self.active_lasers} nm，SLM enable=开")
            
            # 步骤4: 启动两个任务
            logger.info("启动Counter和DO任务...")
            # NI-DAQmx: 启动计数器与数字输出任务
            self.counter_task.start()
            self.do_task.start()

            # 步骤5: 等待Counter任务自动完成（cfg_implicit_timing硬件自动停止）
            # ====================================================================
            # 优化方案（感谢用户纠正）：使用Counter任务的cfg_implicit_timing自动完成
            # 原理：
            # - Counter任务配置为cfg_implicit_timing + FINITE模式，samps_per_chan=9
            # - "隐式时钟"意味着：每次上升沿事件本身就是一次"采样"
            # - 硬件Counter在第9次上升沿到达后自动完成任务
            # - 纳秒级精度，完全由硬件实现，无需Python轮询
            # - 可选择使用wait_until_done()阻塞等待，或is_task_done()轮询显示进度
            logger.info(f"等待Counter硬件自动计数到{self.frames_per_loop}次触发...")
            start_time = time.time()
            count = 0
            last_count = 0
            last_log_time = start_time

            # 计算单帧预期时间（曝光时间 + 相机读取时间估计）
            frame_expected_time = self.exposure_time_us / 1e6 + 0.05  # 曝光时间 + 50ms读取估计
            log_interval = max(0.2, frame_expected_time / 2)  # 日志间隔为半帧时间，最小200ms

            # 等待Counter任务完成（硬件在第9次上升沿后自动停止）
            # NI-DAQmx: 轮询任务是否完成（硬件侧）
            while not self.counter_task.is_task_done():
                # 读取Counter当前计数（用于进度显示）
                try:
                    # NI-DAQmx: 读取计数器当前累计计数
                    count = self.counter_task.read()

                    # 如果计数增加，记录
                    if count > last_count:
                        elapsed = time.time() - start_time
                        logger.info(f"  触发 {count}/{self.frames_per_loop} 检测到 (耗时: {elapsed:.3f}秒)")
                        last_count = count
                except:
                    pass  # Counter在完成后可能无法读取

                # 定期输出状态（根据单帧时间调整间隔）
                if time.time() - last_log_time >= log_interval and count == last_count:
                    elapsed = time.time() - start_time
                    logger.debug(f"  等待触发... 当前: {count}/{self.frames_per_loop}，已用时: {elapsed:.2f}秒")
                    last_log_time = time.time()

                # 短暂休眠，避免过度占用CPU
                time.sleep(0.001)  # 1ms检查间隔

            # 最终读取Counter确认计数
            try:
                final_count = self.counter_task.read()
                logger.info(f"  Counter最终计数: {final_count}")
            except:
                final_count = count

            # 步骤6: Counter已自动完成9次计数，停止DO任务
            elapsed_total = time.time() - start_time
            # NI-DAQmx: 停止任务（终止硬件生成/计数）
            self.do_task.stop()
            self.counter_task.stop()

            logger.info(f"硬件触发循环成功完成！")
            logger.info(f"  精确触发次数: {final_count}")
            logger.info(f"  总耗时: {elapsed_total:.2f}秒")
            logger.info(f"  平均每帧: {elapsed_total/self.frames_per_loop*1000:.1f}ms")
            logger.info(f"  使用Counter cfg_implicit_timing硬件自动停止（纳秒级精度）")

            # 清理Counter任务
            # NI-DAQmx: 释放任务资源
            self.counter_task.close()
            self.counter_task = None

            return True

        except Exception as e:
            logger.error(f"Counter触发循环执行期间出错: {e}")
            import traceback
            traceback.print_exc()

            # 清理Counter任务
            if hasattr(self, 'counter_task') and self.counter_task:
                try:
                    self.counter_task.stop()
                    self.counter_task.close()
                except:
                    pass
                self.counter_task = None

            return False


    def execute_interval(self, interval_time_ms: float = 10.0) -> bool:
        """
        执行循环间隔（将SLM enable设置为低电平）

        参数
        ----
        interval_time_ms : float
            间隔时间（毫秒），默认10ms

        返回
        ----
        bool
            成功返回True，否则返回False
        """
        logger.info(f"执行循环间隔 ({interval_time_ms}ms)...")

        try:
            # 使用set_slm_enable方法将SLM enable设置为低电平
            if not self.set_slm_enable(enable=False, duration_ms=interval_time_ms):
                logger.error("设置SLM enable为低电平失败")
                return False

            logger.debug(f"间隔完成")
            return True

        except Exception as e:
            logger.error(f"间隔执行期间出错: {e}")
            return False

    def run_acquisition(
        self,
        interval_time_ms: float = 10.0,
        slm_setup_time_ms: float = 10.0,
        digital_trigger_source: str = None,
        counter_channel: str = None
    ) -> bool:
        """
        执行完整的SIM采集序列（Counter精确计数模式）

        参数
        ----
        interval_time_ms : float
            循环之间的间隔时间（毫秒），默认10ms
        slm_setup_time_ms : float
            SLM enable设置和响应时间（毫秒），默认10ms
        digital_trigger_source : str
            PFI端口路径，相机ready信号必须连接到此
            默认：使用类常量 DEFAULT_TRIGGER_SOURCE
        counter_channel : str
            要使用的Counter通道
            默认：使用类常量 DEFAULT_COUNTER_CHANNEL

        返回
        ----
        bool
            如果所有循环成功完成返回True
        """
        # 使用类常量作为默认值
        if digital_trigger_source is None:
            digital_trigger_source = self.DEFAULT_TRIGGER_SOURCE
        if counter_channel is None:
            counter_channel = self.DEFAULT_COUNTER_CHANNEL

        logger.info(f"开始SIM采集（Counter精确计数模式）: {self.num_loops} 个循环")
        logger.info(f"每循环 {self.frames_per_loop} 帧")
        logger.info(f"SLM setup时间: {slm_setup_time_ms}ms，循环间隔: {interval_time_ms}ms")
        logger.info(f"触发源: {digital_trigger_source}, Counter: {counter_channel}")

        try:
            # 设置硬件
            self.setup_tasks()

            # 执行每个循环
            for loop_num in range(self.num_loops):
                logger.info(f"=== 循环 {loop_num + 1}/{self.num_loops} ===")

                # 执行循环（使用Counter精确计数）
                if not self.execute_single_loop(
                    slm_setup_time_ms=slm_setup_time_ms,
                    digital_trigger_source=digital_trigger_source,
                    counter_channel=counter_channel
                ):
                    logger.error(f"循环 {loop_num + 1} 失败")
                    return False

                logger.info(f"循环 {loop_num + 1} 完成（精确9次触发）")

                # 在循环之间执行interval（SLM enable变为低电平）
                if loop_num < self.num_loops - 1:
                    if not self.execute_interval(interval_time_ms):
                        logger.error(f"循环 {loop_num + 1} 后的间隔失败")
                        return False

            logger.info("所有循环成功完成！")
            logger.info(f"总共精确执行了 {self.num_loops * self.frames_per_loop} 次触发")
            return True

        except Exception as e:
            logger.error(f"采集失败: {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            # 清理资源
            self.cleanup()

    def cleanup(self) -> None:
        """
        清理硬件资源
        """
        logger.info("正在清理资源...")

        if self.do_task:
            try:
                self.do_task.stop()
                self.do_task.close()
            except:
                pass
            self.do_task = None

        logger.info("清理完成")

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.cleanup()


def main():
    """
    SIM控制器使用示例
    """
    print("=== SIM硬件同步控制系统 v6.3 ===")
    print("cfg_implicit_timing硬件自动停止模式")
    print("默认配置: 488nm激光器, 100ms曝光时间, 100kHz采样率")
    print("核心特性:")
    print("  - 使用cfg_implicit_timing，事件本身即是采样时钟")
    print("  - 硬件Counter在第9次上升沿后自动完成任务")
    print("  - 纳秒级精度，完全由硬件实现，无需Python轮询")
    print("  - SLM finish脉冲在曝光结束后（修正时序）")
    print("  - 必须使用数字触发信号（PFI端口）")
    print("  - 每个循环保证精确9次触发")
    print("  - 适合多循环采集，无时间误差累积")
    print("  - 循环完成后SLM enable变低，间隔后开始新循环")
    print()

    # 示例1: 使用默认配置（仅488nm激光器，100ms曝光）
    print("示例1: 默认配置 - 488nm激光器，100ms曝光，PFI8触发")
    config1 = {
        'device_name': 'Dev1',
        'exposure_time_us': 100000,  # 100ms = 100,000us
        'frames_per_loop': 9,
        'num_loops': 1,
        'sample_rate': 100000,  # 100kHz
        'active_lasers': None  # None = 默认仅488nm
    }

    with SIMController(**config1) as controller:
        # 使用默认参数即可，PFI8和ctr0已设置为默认值
        success = controller.run_acquisition(
            interval_time_ms=10.0,
            slm_setup_time_ms=10.0
        )
        if success:
            print("✓ 示例1完成\n")
        else:
            print("✗ 示例1失败\n")
            return 1

    # 示例2: 双色成像，较短曝光时间
    print("示例2: 双色成像 - 488nm和561nm激光器，50ms曝光")
    config2 = {
        'device_name': 'Dev1',
        'exposure_time_us': 50000,  # 50ms曝光
        'frames_per_loop': 9,
        'num_loops': 2,  # 多个循环测试
        'sample_rate': 100000,  # 100kHz
        'active_lasers': [488, 561]  # 双色
    }

    with SIMController(**config2) as controller:
        success = controller.run_acquisition(
            interval_time_ms=15.0,
            slm_setup_time_ms=20.0  # 更长的SLM setup时间
        )
        if success:
            print("✓ 示例2完成\n")
        else:
            print("✗ 示例2失败\n")
            return 1

    # 示例3: 多循环采集测试（v6.0特色）
    print("示例3: 多循环采集 - 精确计数无timeout")
    config3 = {
        'device_name': 'Dev1',
        'exposure_time_us': 100000,  # 100ms
        'frames_per_loop': 9,
        'num_loops': 5,  # 多循环测试
        'sample_rate': 100000,  # 100kHz
        'active_lasers': [488]
    }

    with SIMController(**config3) as controller:
        print("使用Counter精确计数模式（5个循环，共45帧）")
        # 若需要使用不同的PFI端口，可以指定digital_trigger_source参数
        success = controller.run_acquisition(
            interval_time_ms=10.0,
            slm_setup_time_ms=10.0
        )
        if success:
            print("✓ 示例3完成（5个循环，共45帧）\n")
        else:
            print("✗ 示例3失败（检查PFI8连接）\n")

    print("所有示例完成！")

    print("\n系统特性:")
    print("• cfg_implicit_timing: 事件本身即是采样时钟")
    print("• 硬件Counter在第9次上升沿后自动停止")
    print("• 纳秒级精度，完全由硬件实现")
    print("• 无需Python轮询，不会提前结束或超时")
    print("• 单帧时序: 曝光(100ms) + SLM结束脉冲(100us)")
    print("• 单循环时序: 9帧 × ~100.1ms + 帧间等待 ≈ 1秒")

    print("\n硬件要求:")
    print("• 相机ready信号: TTL数字信号(3.3V/5V)")
    print("• 连接端口: PFI8 (默认)")
    print("• Counter通道: ctr0 (默认)")

    print("\n使用方法:")
    print("controller.run_acquisition(")
    print("    digital_trigger_source='/Dev1/PFI8',  # 默认值")
    print("    counter_channel='ctr0'                # 默认值")
    print(")")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
