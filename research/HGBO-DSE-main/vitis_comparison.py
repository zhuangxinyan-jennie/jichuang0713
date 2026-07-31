#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vitis HLS 2025.1 vs HGBO-DSE Project Optimization Comparison Script
"""

import numpy as np
import yaml

# HGBO-DSE project defined resource weights
WLUT = 0.3
WFF = 0.25
WDSP = 0.3
WBRAM = 0.05

def extract_vitis_metrics():
    """Extract PPA metrics from Vitis HLS 2025.1 synthesis report"""
    # Data extracted from your provided report
    vitis_metrics = {
        'LUT': 8793,
        'FF': 10024,
        'DSP': 0,
        'BRAM': 4,
        'Latency': 713,
        'Critical_Path': 7.742
    }
    return vitis_metrics

def load_baseline_params(config_file):
    """加载基准参数配置文件"""
    with open(config_file, 'r', encoding='utf-8') as f:
        params = yaml.safe_load(f)
    return params

def calculate_normalized_ppa(vitis_metrics, baseline_params):
    """计算归一化的PPA指标"""
    # 提取基准值
    POW = float(baseline_params["POW"][0])
    LTC = float(baseline_params["LATENCY"][0])
    CLK = float(baseline_params["CLK"][0])
    RU = [
        float(baseline_params["LUT"][0]),
        float(baseline_params["FF"][0]),
        float(baseline_params["DSP"][0]),
        float(baseline_params["BRAM"][0])
    ]
    
    # 权重
    wght = [WLUT, WFF, WDSP, WBRAM]
    
    # 计算基准面积
    NUM = sum(np.multiply(wght, RU))
    
    # 提取Vitis结果
    power = vitis_metrics.get('Power', 0.361)  # 如果没有功耗数据，使用基准值
    lat = vitis_metrics['Latency']
    cp = vitis_metrics['Critical_Path']
    usg = [
        vitis_metrics['LUT'],
        vitis_metrics['FF'],
        vitis_metrics['DSP'],
        vitis_metrics['BRAM']
    ]
    
    # 计算面积
    area = sum(np.multiply(wght, usg))
    
    # 归一化PLCA指标
    npower = power / POW
    nlat = lat / LTC
    ncp = cp / CLK
    narea = area / NUM
    
    return {
        'normalized_power': npower,
        'normalized_latency': nlat,
        'normalized_critical_path': ncp,
        'normalized_area': narea,
        'raw_metrics': vitis_metrics
    }

def main():
    print("=== Vitis HLS 2025.1 与 HGBO-DSE 项目优化效果比较 ===\n")
    
    # 1. 提取Vitis HLS 2025.1的PPA指标
    print("1. 提取Vitis HLS 2025.1的PPA指标:")
    vitis_metrics = extract_vitis_metrics()
    for key, value in vitis_metrics.items():
        print(f"   {key}: {value}")
    
    # 2. 加载基准参数
    print("\n2. 加载基准参数配置:")
    try:
        baseline_params = load_baseline_params('config/MachSuite/aes_aes_vitis2025_params.yaml')
        print("   基准参数加载成功")
        print(f"   基准功耗: {baseline_params['POW'][0]}")
        print(f"   基准延迟: {baseline_params['LATENCY'][0]}")
        print(f"   基准时钟: {baseline_params['CLK'][0]}")
        print(f"   基准LUT: {baseline_params['LUT'][0]}")
        print(f"   基准FF: {baseline_params['FF'][0]}")
        print(f"   基准DSP: {baseline_params['DSP'][0]}")
        print(f"   基准BRAM: {baseline_params['BRAM'][0]}")
    except FileNotFoundError:
        print("   警告: 未找到基准配置文件，使用默认值")
        baseline_params = {
            'POW': [0.361],
            'LATENCY': [713],
            'CLK': [7.742],
            'LUT': [8793],
            'FF': [10024],
            'DSP': [0],
            'BRAM': [4]
        }
    
    # 3. 计算归一化PPA指标
    print("\n3. 计算归一化PPA指标:")
    normalized_results = calculate_normalized_ppa(vitis_metrics, baseline_params)
    
    print(f"   归一化功耗: {normalized_results['normalized_power']:.4f}")
    print(f"   归一化延迟: {normalized_results['normalized_latency']:.4f}")
    print(f"   归一化关键路径: {normalized_results['normalized_critical_path']:.4f}")
    print(f"   归一化面积: {normalized_results['normalized_area']:.4f}")
    
    # 4. 解释比较方法
    print("\n4. 比较方法说明:")
    print("   - 归一化指标 < 1.0: 表示比基准性能更好")
    print("   - 归一化指标 = 1.0: 表示与基准性能相同")
    print("   - 归一化指标 > 1.0: 表示比基准性能更差")
    print("   - 对于多目标优化，通常使用Pareto前沿进行比较")
    
    # 5. 计算综合评分
    print("\n5. 综合评分计算:")
    # 使用与HGBO-DSE项目相同的权重计算综合评分
    wght = [WLUT, WFF, WDSP, WBRAM]
    RU = [
        float(baseline_params["LUT"][0]),
        float(baseline_params["FF"][0]),
        float(baseline_params["DSP"][0]),
        float(baseline_params["BRAM"][0])
    ]
    NUM = sum(np.multiply(wght, RU))
    
    # 计算Vitis结果的加权面积
    vitis_area = sum(np.multiply(wght, [
        vitis_metrics['LUT'],
        vitis_metrics['FF'],
        vitis_metrics['DSP'],
        vitis_metrics['BRAM']
    ]))
    
    normalized_area = vitis_area / NUM
    print(f"   Vitis HLS 2025.1 归一化面积评分: {normalized_area:.4f}")
    
    if normalized_area < 1.0:
        print("   ✓ Vitis HLS 2025.1 在面积优化方面表现良好")
    elif normalized_area == 1.0:
        print("   = Vitis HLS 2025.1 在面积优化方面与基准相同")
    else:
        print("   ✗ Vitis HLS 2025.1 在面积优化方面表现较差")
    
    print("\n6. 与HGBO-DSE项目比较的建议:")
    print("   - 运行HGBO-DSE项目在相同基准配置下的优化")
    print("   - 比较两者的归一化PPA指标")
    print("   - 使用Pareto前沿分析多目标优化效果")
    print("   - 考虑功耗、延迟、关键路径和面积的综合权衡")

if __name__ == "__main__":
    main()
