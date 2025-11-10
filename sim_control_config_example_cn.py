"""
SIM控制系统 - 配置示例和高级使用方法
====================================

本文件提供SIM硬件同步控制器的各种配置示例和高级使用模式。

作者: Generated with Claude Code
日期: 2025-10-29
"""

from sim_control_synchronized import SIMController
import logging

# 配置详细日志用于调试
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('sim_acquisition.log'),
        logging.StreamHandler()
    ]
)


# ==============================================================================
# 示例 1: 默认设置的基础采集
# ==============================================================================
def example_basic_acquisition():
    """
    使用默认设置的简单采集
    """
    print("\n=== 示例 1: 基础采集 ===")

    with SIMController(
        device_name='Dev1',
        exposure_time_us=10000,  # 10ms曝光
        frames_per_loop=9,       # 标准SIM模式
        num_loops=1              # 单次采集
    ) as controller:
        controller.run_acquisition()


# ==============================================================================
# 示例 2: 高速采集（短曝光）
# ==============================================================================
def example_high_speed_acquisition():
    """
    使用短曝光时间的高速成像
    适用于快速动态过程或明亮样品
    """
    print("\n=== 示例 2: 高速采集 ===")

    with SIMController(
        device_name='Dev1',
        exposure_time_us=1000,   # 1ms曝光（快速）
        frames_per_loop=9,
        num_loops=10,            # 10次采集
        sample_rate=1000000      # 1 MHz用于1us精度
    ) as controller:
        controller.run_acquisition()


# ==============================================================================
# 示例 3: 弱信号长曝光
# ==============================================================================
def example_long_exposure():
    """
    用于弱荧光信号的长曝光采集
    """
    print("\n=== 示例 3: 长曝光采集 ===")

    with SIMController(
        device_name='Dev1',
        exposure_time_us=100000,  # 100ms曝光（长）
        frames_per_loop=9,
        num_loops=1,
        sample_rate=1000000
    ) as controller:
        controller.run_acquisition()


# ==============================================================================
# 示例 4: 延时SIM成像
# ==============================================================================
def example_timelapse_imaging():
    """
    多循环延时SIM成像
    每个循环代表一个时间点
    """
    print("\n=== 示例 4: 延时SIM成像 ===")

    with SIMController(
        device_name='Dev1',
        exposure_time_us=20000,   # 20ms曝光
        frames_per_loop=9,
        num_loops=100,           # 100个时间点
        sample_rate=1000000
    ) as controller:
        success = controller.run_acquisition()

        if success:
            print(f"成功采集 {100} 个时间点！")
        else:
            print("延时采集失败！")


# ==============================================================================
# 示例 5: 自定义帧数（非标准SIM）
# ==============================================================================
def example_custom_frame_count():
    """
    使用不同帧数的非标准SIM模式
    用于实验性SIM变体或测试
    """
    print("\n=== 示例 5: 自定义帧数 ===")

    with SIMController(
        device_name='Dev1',
        exposure_time_us=15000,
        frames_per_loop=15,      # 15帧而不是标准的9帧
        num_loops=5,
        sample_rate=1000000
    ) as controller:
        controller.run_acquisition()


# ==============================================================================
# 示例 6: 超高精度时序（亚微秒级）
# ==============================================================================
def example_ultra_precision():
    """
    使用更高采样率实现最大时序精度
    需要DAQ硬件支持高时基
    """
    print("\n=== 示例 6: 超高精度 ===")

    with SIMController(
        device_name='Dev1',
        exposure_time_us=5000,
        frames_per_loop=9,
        num_loops=1,
        sample_rate=10000000     # 10 MHz = 100ns精度
    ) as controller:
        # 注意：如果sample_rate改变，需要调整exposure_time_us的计算
        # 在10 MHz时，1个采样点 = 0.1 us
        controller.run_acquisition()


# ==============================================================================
# 示例 7: 逐步执行的手动控制
# ==============================================================================
def example_manual_control():
    """
    用于调试或自定义的采集步骤手动控制
    """
    print("\n=== 示例 7: 手动控制 ===")

    controller = SIMController(
        device_name='Dev1',
        exposure_time_us=10000,
        frames_per_loop=9,
        num_loops=1
    )

    try:
        # 步骤1: 设置硬件
        print("步骤1: 正在设置硬件任务...")
        controller.setup_tasks()

        # 步骤2: 启动AI任务
        print("步骤2: 正在启动模拟输入监测...")
        controller.ai_task.start()

        # 步骤3: 等待相机就绪
        print("步骤3: 正在等待相机就绪信号...")
        if not controller.wait_for_camera_ready():
            print("错误: 相机未就绪！")
            return

        # 步骤4: 执行循环
        print("步骤4: 正在执行采集循环...")
        controller.execute_single_loop()

        print("手动采集完成！")

    finally:
        # 始终清理
        controller.cleanup()


# ==============================================================================
# 示例 8: 硬件配置指南
# ==============================================================================
def print_hardware_configuration_guide():
    """
    显示硬件连接和配置信息
    """
    print("\n" + "=" * 70)
    print("SIM硬件配置指南")
    print("=" * 70)

    print("\n1. 数字输出连接 (NI DAQ → 设备)")
    print("-" * 70)
    print("   端口/线路          |  连接设备             |  信号类型")
    print("-" * 70)
    print("   Dev1/port0/line0   -> 相机触发           -> 电平（高电平有效）")
    print("   Dev1/port0/line1   -> 激光器触发         -> 电平（高电平有效）")
    print("   Dev1/port0/line2   -> SLM使能            -> 电平（高电平有效）")
    print("   Dev1/port0/line3   -> SLM触发            -> 边沿（上升沿）")
    print("   Dev1/port0/line4   -> SLM结束            -> 边沿（上升沿）")

    print("\n2. 模拟输入连接 (设备 → NI DAQ)")
    print("-" * 70)
    print("   设备输出           |  DAQ输入              |  信号范围")
    print("-" * 70)
    print("   相机就绪           -> Dev1/ai0            -> 0-10V (阈值: 2.5V)")

    print("\n3. 信号时序图")
    print("-" * 70)
    print("\n   单帧时序 (曝光 = 10ms 示例):")
    print("   ")
    print("   相机触发:  |‾‾‾‾‾‾‾‾‾‾|________")
    print("   激光触发:  |‾‾‾‾‾‾‾‾‾‾|________")
    print("   SLM使能:   |‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾")
    print("   SLM触发:   |‾|________________")
    print("   SLM结束:   _________|‾|_______")
    print("              <--10ms-->")

    print("\n   多帧循环 (9帧):")
    print("   ")
    print("   SLM使能:   |‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾|______")
    print("   帧触发:    |‾||‾||‾||‾||‾||‾||‾||‾||‾|______")
    print("   相机就绪:  ___|‾‾|_|‾‾|_|‾‾|_|‾‾|.....")
    print("              <- 帧1 ->< 帧2 -> ...")

    print("\n4. 软件配置参数")
    print("-" * 70)
    print("   device_name:       NI DAQ设备标识符 (例如: 'Dev1')")
    print("   exposure_time_us:  相机/激光器曝光时间（微秒）")
    print("   frames_per_loop:   每个SIM模式的帧数（通常为9）")
    print("   num_loops:         总采集循环数")
    print("   sample_rate:       DAQ采样时钟频率 (Hz)")
    print("                      - 1 MHz = 1 us分辨率（推荐）")
    print("                      - 10 MHz = 0.1 us分辨率（如果支持）")

    print("\n5. 外部设备设置（在设备软件中配置）")
    print("-" * 70)
    print("   相机 (HCImage软件):")
    print("   - 触发模式:        外部电平触发")
    print("   - 触发极性:        高电平有效")
    print("   - 曝光控制:        外部（由NI DAQ控制）")
    print("   - 帧大小:          根据需要配置")
    print("   - 像素合并:        根据需要配置")
    print("   ")
    print("   激光器控制器:")
    print("   - 触发模式:        外部")
    print("   - 触发极性:        高电平有效")
    print("   - 功率:            设置到所需水平")
    print("   ")
    print("   SLM控制器:")
    print("   - 使能模式:        电平触发")
    print("   - 触发模式:        边沿触发（上升沿）")
    print("   - 结束模式:        边沿触发（上升沿）")
    print("   - 图案序列:        在SLM软件中配置9个图案")

    print("\n6. 时序精度注意事项")
    print("-" * 70)
    print("   - 硬件定时操作确保微秒级精度")
    print("   - 典型抖动: < 1微秒")
    print("   - 受限于DAQ硬件时基（通常为20-100 MHz）")
    print("   - 相机就绪的软件轮询增加约100-1000 us延迟")
    print("   - 对于关键时序，使用硬件触发而不是轮询")

    print("\n7. 故障排除")
    print("-" * 70)
    print("   问题: 相机未触发")
    print("   -> 检查到Dev1/port0/line0的电缆连接")
    print("   -> 验证相机处于外部触发模式")
    print("   -> 确认触发电压电平（应为3.3V或5V逻辑）")
    print("   ")
    print("   问题: SLM未更新图案")
    print("   -> 验证SLM使能、触发和结束连接")
    print("   -> 检查SLM软件配置为外部控制")
    print("   -> 确认边沿触发极性（上升沿 vs 下降沿）")
    print("   ")
    print("   问题: 激光器未发光")
    print("   -> 检查到Dev1/port0/line1的连接")
    print("   -> 验证激光器控制器外部触发设置")
    print("   -> 确认激光器安全互锁已满足")
    print("   ")
    print("   问题: 相机就绪超时")
    print("   -> 检查模拟输入连接（Dev1/ai0）")
    print("   -> 验证相机就绪信号为0-10V范围")
    print("   -> 如需要调整READY_SIGNAL_THRESHOLD（默认2.5V）")
    print("   -> 如果相机初始化慢，增加超时时间")

    print("\n" + "=" * 70 + "\n")


# ==============================================================================
# 示例 9: 测试各个组件
# ==============================================================================
def test_digital_outputs():
    """
    独立测试数字输出，不进行完整采集
    """
    print("\n=== 测试数字输出 ===")

    import nidaqmx
    from nidaqmx.constants import LineGrouping
    import time

    device = 'Dev1'

    with nidaqmx.Task() as task:
        # 添加所有数字输出线路
        task.do_channels.add_do_chan(
            f"{device}/port0/line0:4",
            line_grouping=LineGrouping.CHAN_PER_LINE
        )

        print("正在测试每个输出线路...")

        # 依次测试每条线路
        for line in range(5):
            print(f"  激活线路 {line}...")
            data = [0] * 5
            data[line] = 1
            task.write(data)
            time.sleep(1)  # 保持1秒

        # 全部关闭
        print("  所有线路关闭")
        task.write([0, 0, 0, 0, 0])

    print("数字输出测试完成！")


def test_analog_input():
    """
    独立测试模拟输入监测
    """
    print("\n=== 测试模拟输入 ===")

    import nidaqmx
    from nidaqmx.constants import TerminalConfiguration, VoltageUnits
    import numpy as np
    import time

    device = 'Dev1'

    with nidaqmx.Task() as task:
        task.ai_channels.add_ai_voltage_chan(
            physical_channel=f"{device}/ai0",
            terminal_config=TerminalConfiguration.RSE,
            min_val=0.0,
            max_val=10.0,
            units=VoltageUnits.VOLTS
        )

        print("正在读取模拟输入（10个采样点）...")

        for i in range(10):
            voltage = task.read()
            print(f"  采样 {i+1}: {voltage:.3f} V")
            time.sleep(0.1)

    print("模拟输入测试完成！")


# ==============================================================================
# 主菜单
# ==============================================================================
def main():
    """
    选择示例的主菜单
    """
    print("\n" + "=" * 70)
    print("SIM控制系统 - 配置示例")
    print("=" * 70)
    print("\n选择要运行的示例:")
    print("  1. 基础采集")
    print("  2. 高速采集")
    print("  3. 长曝光")
    print("  4. 延时成像")
    print("  5. 自定义帧数")
    print("  6. 超高精度")
    print("  7. 手动控制")
    print("  8. 硬件配置指南")
    print("  9. 测试数字输出")
    print(" 10. 测试模拟输入")
    print("  0. 退出")
    print("-" * 70)

    while True:
        try:
            choice = input("\n输入选择 (0-10): ").strip()

            if choice == '0':
                print("正在退出...")
                break
            elif choice == '1':
                example_basic_acquisition()
            elif choice == '2':
                example_high_speed_acquisition()
            elif choice == '3':
                example_long_exposure()
            elif choice == '4':
                example_timelapse_imaging()
            elif choice == '5':
                example_custom_frame_count()
            elif choice == '6':
                example_ultra_precision()
            elif choice == '7':
                example_manual_control()
            elif choice == '8':
                print_hardware_configuration_guide()
            elif choice == '9':
                test_digital_outputs()
            elif choice == '10':
                test_analog_input()
            else:
                print("无效选择！请输入0-10。")

        except KeyboardInterrupt:
            print("\n\n用户中断。正在退出...")
            break
        except Exception as e:
            print(f"\n错误: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
