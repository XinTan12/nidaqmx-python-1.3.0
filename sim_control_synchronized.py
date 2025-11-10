# -*- coding: utf-8 -*-
"""
SIM 硬件同步控制（中文注释版，UTF-8）

核心方案：
- 单个硬件定时 DO 任务（按端口位掩码写入）+ retriggerable 单帧重放；
- 计数器使用隐式时钟（cfg_implicit_timing + FINITE），“事件=采样”，计满 N 次自动完成；
- 每个 loop 开始时记录时间戳，loop 结束后根据 loop_start_spacing_ms（两个 loop 开始之间的目标间隔，毫秒）
  计算剩余时间，在剩余时间内仅拉低 Enable，保证下一个 loop 准时开始。
"""

import time
import threading
import logging
from typing import Optional, List

import numpy as np
import nidaqmx
from nidaqmx.constants import AcquisitionType, LineGrouping, Edge, CountDirection
from nidaqmx.stream_writers import DigitalSingleChannelWriter


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SIMController:
    """SIM 成像硬件定时同步控制器"""

    # Port0 线路映射（line 编号 → 设备功能）
    CAM_TRIGGER_LINE = 0
    LASER_405_LINE = 1
    LASER_488_LINE = 2
    LASER_561_LINE = 3
    LASER_647_LINE = 4
    SLM_ENABLE_LINE = 5
    SLM_TRIGGER_LINE = 6
    SLM_FINISH_LINE = 7

    # 激光器波长常量（用于选择激活的激光）
    LASER_405 = 405
    LASER_488 = 488
    LASER_561 = 561
    LASER_647 = 647

    # 默认参数
    DEFAULT_SAMPLE_RATE = 100_000         # 100 kHz（10 微秒分辨率）
    DEFAULT_TRIGGER_SOURCE = "/Dev1/PFI8"  # 相机 Ready 触发源（PFI 终端路径）
    DEFAULT_COUNTER_CHANNEL = "ctr0"       # 计数器通道名称（Dev1/ctr0）

    def __init__(
        self,
        device_name: str = "Dev1",
        exposure_time_us: float = 100_000,
        frames_per_loop: int = 9,
        num_loops: int = 1,
        sample_rate: float = DEFAULT_SAMPLE_RATE,
        active_lasers: Optional[List[int]] = None,
    ):
        self.device_name = device_name
        self.exposure_time_us = exposure_time_us
        self.frames_per_loop = frames_per_loop
        self.num_loops = num_loops
        self.sample_rate = sample_rate

        # 处理激光器选择（默认仅 488nm）
        if active_lasers is None:
            self.active_lasers = [self.LASER_488]
        else:
            valid = {self.LASER_405, self.LASER_488, self.LASER_561, self.LASER_647}
            invalid = set(active_lasers) - valid
            if invalid:
                raise ValueError(f"无效的激光器波长: {invalid}")
            self.active_lasers = list(active_lasers)

        self.laser_line_map = {
            self.LASER_405: self.LASER_405_LINE,
            self.LASER_488: self.LASER_488_LINE,
            self.LASER_561: self.LASER_561_LINE,
            self.LASER_647: self.LASER_647_LINE,
        }

        # 曝光对应的采样点数（由采样率换算）
        self.exposure_samples = int(exposure_time_us / (1e6 / sample_rate))

        # 任务句柄
        self.do_task: Optional[nidaqmx.Task] = None
        self.counter_task: Optional[nidaqmx.Task] = None

        logger.info("SIM 控制器已初始化")
        logger.info(f"  设备: {device_name}")
        logger.info(f"  曝光时间: {exposure_time_us} 微秒")
        logger.info(f"  每循环帧数: {frames_per_loop}")
        logger.info(f"  循环次数: {num_loops}")
        logger.info(f"  采样率: {sample_rate} Hz")

    def setup_tasks(self) -> None:
        """
        创建 DO 任务（按端口级别合并为单通道，硬件定时）。

        说明：
        - add_do_chan(..., line_grouping=CHAN_FOR_ALL_LINES) 将整端口视为单通道；
        - 与 DigitalSingleChannelWriter.write_many_sample_port_uint16(bitmasks) 搭配，
          每个采样点用一个 uint16 位掩码表示端口所有线的电平（bit0 → line0）。
        """
        self.do_task = nidaqmx.Task("DO_Control_Task")
        do_lines = f"{self.device_name}/port0/line{self.CAM_TRIGGER_LINE}:{self.SLM_FINISH_LINE}"
        self.do_task.do_channels.add_do_chan(
            lines=do_lines,
            line_grouping=LineGrouping.CHAN_FOR_ALL_LINES,
        )
        self.do_task.timing.cfg_samp_clk_timing(
            rate=self.sample_rate,
            sample_mode=AcquisitionType.FINITE,
            samps_per_chan=10_000,
        )

    def generate_frame_waveform(self) -> np.ndarray:
        """
        生成单帧 0/1 波形矩阵（形状：8 x samples）。

        规则：
        - 相机触发/激光：在曝光期间为高；
        - SLM enable：整帧为高；
        - SLM trigger：帧开始 100 微秒；
        - SLM finish：曝光结束后 100 微秒。
        """
        trigger_high_samples = self.exposure_samples
        trigger_edge_samples = max(1, int(100 / (1e6 / self.sample_rate)))  # 100 us 脉冲
        total_samples = trigger_high_samples + trigger_edge_samples

        w = np.zeros((8, total_samples), dtype=np.uint8)
        # 相机触发：曝光期间为高
        w[self.CAM_TRIGGER_LINE, 0:trigger_high_samples] = 1
        # 激光：激活的波长在曝光期间为高
        for wl in self.active_lasers:
            w[self.laser_line_map[wl], 0:trigger_high_samples] = 1
        # SLM enable：整帧为高
        w[self.SLM_ENABLE_LINE, :] = 1
        # SLM trigger：帧开始 100 us
        w[self.SLM_TRIGGER_LINE, 0:trigger_edge_samples] = 1
        # SLM finish：曝光结束后 100 us
        finish_start = trigger_high_samples
        w[self.SLM_FINISH_LINE, finish_start:finish_start + trigger_edge_samples] = 1
        return w

    @staticmethod
    def _pack_waveform_to_port_uint16(waveform: np.ndarray) -> np.ndarray:
        """
        将 (lines, samples) 的 0/1 波形打包为 1D uint16 端口位掩码序列。
        - CHAN_FOR_ALL_LINES 模式下，NI-DAQmx 期望每个采样点是一个端口位掩码；
        - USB‑6423 的 Port0 最多 16 条线，因此使用 uint16 覆盖 bit0..bit15；
        - bit0 对应 line0，bit1 对应 line1，依此类推。
        """
        if waveform.ndim != 2:
            raise ValueError("waveform must be 2D (lines, samples)")
        lines, samples = waveform.shape
        if lines > 16:
            raise ValueError("supports up to 16 lines")
        wf = waveform.astype(np.uint16, copy=False)
        weights = (np.uint16(1) << np.arange(lines, dtype=np.uint16))[:, None]
        return np.bitwise_or.reduce(weights * wf, axis=0)

    def set_slm_enable(self, enable: bool, duration_ms: float = 1.0) -> bool:
        """
        立即播放一段短波形，将 SLM Enable 置高/低，持续指定时长。
        实现：禁用开始触发 → 写入端口位掩码序列 → start → wait → stop。
        """
        try:
            try:
                self.do_task.triggers.start_trigger.disable_start_trig()
            except Exception:
                pass

            duration_samples = int((duration_ms * 1000) / (1e6 / self.sample_rate))
            if duration_samples <= 0:
                return True

            w = np.zeros((8, duration_samples), dtype=np.uint8)
            if enable:
                w[self.SLM_ENABLE_LINE, :] = 1

            self.do_task.timing.samp_quant_samp_per_chan = duration_samples
            writer = DigitalSingleChannelWriter(self.do_task.out_stream)
            packed = self._pack_waveform_to_port_uint16(w)
            writer.write_many_sample_port_uint16(packed)

            self.do_task.start()
            self.do_task.wait_until_done(timeout=max(1.0, duration_ms / 1000.0 + 0.5))
            self.do_task.stop()
            return True
        except Exception as e:
            logger.error(f"设置 SLM Enable 失败: {e}")
            return False

    def execute_single_loop(
        self,
        digital_trigger_source: str = None,
        counter_channel: str = None,
    ) -> bool:
        """
        执行一个 loop（N 帧）：
        - Counter：边沿计数 + 隐式时钟 + 有限采样（N 次事件自动完成）；
        - DO：写入“单帧”缓冲，配置数字开始触发为相机 Ready，并允许 retriggerable；
        - 结束：等待第 N 帧完整输出再停止任务，避免最后一帧被截断。
        """
        if digital_trigger_source is None:
            digital_trigger_source = self.DEFAULT_TRIGGER_SOURCE
        if counter_channel is None:
            counter_channel = self.DEFAULT_COUNTER_CHANNEL

        try:
            # Counter：边沿计数 + 隐式时钟（FINITE N 事件）
            self.counter_task = nidaqmx.Task("CounterTask")
            ctr_path = f"{self.device_name}/{counter_channel}"
            ci = self.counter_task.ci_channels.add_ci_count_edges_chan(
                ctr_path, edge=Edge.RISING, initial_count=0, count_direction=CountDirection.COUNT_UP
            )
            ci.ci_count_edges_term = digital_trigger_source
            self.counter_task.timing.cfg_implicit_timing(
                sample_mode=AcquisitionType.FINITE,
                samps_per_chan=self.frames_per_loop,
            )

            # loop 前：SLM Enable 预置为高（系统默认 1 ms）
            if not self.set_slm_enable(True):
                logger.error("loop 前 SLM Enable 预置失败")
                self.counter_task.close(); self.counter_task = None
                return False

            # DO：单帧缓冲 + retriggerable（每个 Ready 上升沿重放一帧）
            frame_wf = self.generate_frame_waveform()
            frame_samples = frame_wf.shape[1]
            self.do_task.timing.samp_quant_samp_per_chan = frame_samples
            self.do_task.triggers.start_trigger.cfg_dig_edge_start_trig(
                trigger_source=digital_trigger_source, trigger_edge=Edge.RISING
            )
            self.do_task.triggers.start_trigger.retriggerable = True

            writer = DigitalSingleChannelWriter(self.do_task.out_stream)
            packed = self._pack_waveform_to_port_uint16(frame_wf)
            writer.write_many_sample_port_uint16(packed)

            # 启动任务
            self.counter_task.start()
            self.do_task.start()

            # 等待 Counter 完成（优先使用“完成事件回调”，否则退回阻塞等待）
            done_evt = threading.Event()

            def _counter_done_cb(task_handle, status, callback_data):
                try:
                    done_evt.set()
                except Exception:
                    pass
                return 0  # 回调必须返回 0

            used_callback = False
            try:
                self.counter_task.register_done_event(_counter_done_cb)
                used_callback = True
            except Exception:
                used_callback = False

            waveform_time_s = frame_samples / self.sample_rate
            frame_expected_time = waveform_time_s + 0.012
            loop_timeout = self.frames_per_loop * frame_expected_time * 1.2  # 安全系数 1.2×

            if used_callback:
                logger.info("计时器等待策略：完成事件回调（Done event）+ 线程事件等待")
                if not done_evt.wait(timeout=loop_timeout):
                    logger.error("Counter 等待超时（回调未触发）")
            else:
                logger.info("计时器等待策略：阻塞等待（wait_until_done）")
                self.counter_task.wait_until_done(timeout=loop_timeout)

            # 确保最后一帧完整输出（按 1.2× 单帧时长等待）
            try:
                self.do_task.wait_until_done(timeout=frame_expected_time * 1.2)
            except Exception:
                pass

            # 追加“全低尾段”（例如 1 ms），使端口在停止后保持低电平
            try:
                # 先确保当前运行段已停止，再配置并播放尾段
                try:
                    self.do_task.stop()
                except Exception:
                    pass

                # 禁用开始触发，立即播放
                try:
                    self.do_task.triggers.start_trigger.disable_start_trig()
                except Exception:
                    pass

                tail_ms = 1.0
                tail_samples = max(1, int((tail_ms * 1e-3) * self.sample_rate))
                self.do_task.timing.samp_quant_samp_per_chan = tail_samples
                writer = DigitalSingleChannelWriter(self.do_task.out_stream)
                zero_masks = np.zeros(tail_samples, dtype=np.uint16)
                writer.write_many_sample_port_uint16(zero_masks)

                self.do_task.start()
                self.do_task.wait_until_done(timeout=max(0.5, tail_ms/1000.0 + 0.1))
                self.do_task.stop()
            except Exception:
                pass

            # 停止任务
            self.do_task.stop()
            self.counter_task.stop()

            self.counter_task.close(); self.counter_task = None
            return True
        except Exception as e:
            logger.error(f"执行单个 loop 失败: {e}")
            try:
                if self.counter_task:
                    self.counter_task.stop(); self.counter_task.close()
            except Exception:
                pass
            self.counter_task = None
            return False

    def execute_interval(self, interval_time_ms: float = 10.0) -> bool:
        """
        loop 之间的“间隔段”：仅将 SLM Enable 置为低电平、保持指定时长。
        说明：单帧波形结束时，除 Enable 外，其余线均为 0，因此间隔阶段只需拉低 Enable。
        """
        return self.set_slm_enable(False, interval_time_ms)

    def run_acquisition(
        self,
        digital_trigger_source: str = None,
        counter_channel: str = None,
        loop_start_spacing_ms: float = 2000.0,
    ) -> bool:
        """
        执行多次 loop，并使用“两个 loop 开始之间的目标间隔”（毫秒）来安排间隔：
        - 每个 loop 开始时记录时间戳；
        - loop 完成后按目标间隔计算剩余时间，仅在剩余时间内拉低 Enable，保证下一个 loop 准时开始。
        说明：
        - digital_trigger_source: 相机 Ready 触发源（PFI 终端路径）；
        - counter_channel: 计数器通道名称（如 "ctr0"）。
        该方法会在结束后自动调用 cleanup() 清理任务。
        """
        if digital_trigger_source is None:
            digital_trigger_source = self.DEFAULT_TRIGGER_SOURCE
        if counter_channel is None:
            counter_channel = self.DEFAULT_COUNTER_CHANNEL

        logger.info(f"开始采集：共 {self.num_loops} 张图片，每张包含 {self.frames_per_loop} 帧")
        try:
            self.setup_tasks()
            for i in range(self.num_loops):
                logger.info(f"=== 正在采集第 {i+1}/{self.num_loops} 张图片 ===")
                loop_start_ts = time.time()

                if not self.execute_single_loop(
                    digital_trigger_source=digital_trigger_source,
                    counter_channel=counter_channel,
                ):
                    logger.error(f"第 {i+1} 张图片采集失败")
                    return False

                logger.info(f"第 {i+1} 张图片采集完成")

                if i < self.num_loops - 1:
                    interval_ts = loop_start_ts + loop_start_spacing_ms / 1000.0
                    now = time.time()
                    remain_ms = max(0.0, (interval_ts - now) * 1000.0)
                    if remain_ms <= 0:
                        logger.warning("本次图片采集用时超过设定的开始间隔，跳过间隔阶段")
                    else:
                        # 仅等待剩余时间，不输出间隔波形（端口已由尾段保持为低电平）
                        time.sleep(remain_ms / 1000.0)

            logger.info("所有图片采集已完成")
            logger.info(f"总触发次数: {self.num_loops * self.frames_per_loop}")
            return True
        except Exception as e:
            logger.error(f"采集失败: {e}")
            return False
        finally:
            self.cleanup()

    def cleanup(self) -> None:
        logger.info("正在清理...")
        try:
            if self.do_task:
                self.do_task.stop(); self.do_task.close()
        except Exception:
            pass
        self.do_task = None
        logger.info("清理完成")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.cleanup()


def main() -> int:
    print("=== SIM 硬件同步控制（DO + Counter）演示 ===")
    print("方案要点：")
    print("  • 单个 DO 任务（端口位掩码写）+ retriggerable 单帧重放")
    print("  • 计数器隐式时钟（FINITE）：事件=采样，N 次自动完成")
    print("  • 支持设定“两个 loop 开始之间”的时间间隔（loop_start_spacing_ms）")
    print()
    print("接线概要：")
    print("  • DO: Dev1/port0/line0..7 → 相机触发、激光 TTL、SLM 三线")
    print("  • Ready 触发: /Dev1/PFI8（可在参数中改为其它 PFI）")
    print("  • 计数器: Dev1/ctr0（PFI8 路由到计数器输入）")
    print()
    print("使用示例（可按需修改）：")
    print("  device_name='Dev1'")
    print("  exposure_time_us=100000   # 100 ms 曝光 ≈ 在 100 kHz 下 10000 点")
    print("  frames_per_loop=9         # 单个 loop 的帧数")
    print("  num_loops=1               # loop 次数")
    print("  sample_rate=100000        # 100 kHz（10 微秒/点）")
    print("  active_lasers=None        # None=默认仅 488 nm；或 [405,488,561,647]")
    print("  loop_start_spacing_ms=2000.0  # 两个 loop 开始之间的目标间隔（毫秒）")

    cfg = dict(
        device_name='Dev1',
        exposure_time_us=100000,
        frames_per_loop=9,
        num_loops=1,
        sample_rate=100000,
        active_lasers=None,
    )

    print("开始运行…\n")
    with SIMController(**cfg) as c:
        ok = c.run_acquisition(
         loop_start_spacing_ms=2000.0,
        )
        print("运行结果：成功" if ok else "运行结果：失败")
        if not ok:
            print("排查建议：")
            print("  1) 检查 Ready 线是否接到指定 PFI（默认 /Dev1/PFI8）")
            print("  2) 检查 DO 口逻辑族在 NI MAX 中是否配置为 3.3 V")
            print("  3) 确认 retriggerable 已开启、采样率与曝光换算是否合理")
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())


