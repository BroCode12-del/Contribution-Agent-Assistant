from pathlib import Path

import numpy as np
import pandas as pd


def clean_data():
    data_folder = Path(__file__).resolve().parent / 'data'

    fps = pd.read_csv(
        data_folder / 'gaming_fps_dataset.csv'
        )
    cpu = pd.read_csv(data_folder / 'cpu_specifications.csv')
    gpu = pd.read_csv(data_folder / 'gpu_1986-2026.csv')

    cpu[[
        'Name_cpu',
        'Cores_Threads',
        'Clock_Frequency',
        'Socket',
        'Process_Size',
        'L3_Cache',
        'TDP',
        'Released',
        'cpu_key'
    ]].copy()

    gpu[[
        'Name_gpu',
        'Graphics Processor__Architecture',
        'Clock Speeds__Base Clock',
        'Clock Speeds__Boost Clock',
        'Memory__Memory Size',
        'Memory__Memory Type',
        'Memory__Memory Bus',
        'Memory__Bandwidth',
        'Board Design__TDP',
        'Top__CORES',
        'Render Config__Shading Units',
        'Render Config__RT Cores',
        'Theoretical Performance__FP32 (float)',
        'gpu_key'
        ]].copy()

    fps[[
    'gpu_name',
    'cpu_name',
    'demand_score',
    'resolution',
    'preset',
    'ray_tracing',
    'rt_quality',
    'upscaling',
    'upscaling_quality',
    'engine',
    'game',
    'gpu_key',
    'cpu_key',
    'avg_fps'
    ]].copy()

# Clean CPU
    cpu[['cores', 'threads']] = (
    cpu['Cores_Threads'].astype(str).str.split('/', n=1, expand=True)
    .reindex(columns=[0, 1])
)
    cpu['cores'] = pd.to_numeric(cpu['cores'], errors='coerce')
    cpu['threads'] = pd.to_numeric(cpu['threads'], errors='coerce')
    cpu['cores'] = cpu['cores'].astype('Int64')
    cpu['threads'] = cpu['threads'].astype('Int64')
    cpu = cpu.drop(columns=['Cores_Threads'])

    cpu[['base_clock', 'boost_clock']] = (
    cpu['Clock_Frequency'].str.replace('GHz', '', case=False, regex=False)
    .str.split('to', n=1, expand=True).reindex(columns=[0, 1])
)
    cpu['base_clock'] = pd.to_numeric(cpu['base_clock'], errors='coerce')
    cpu['boost_clock'] = pd.to_numeric(cpu['boost_clock'], errors='coerce')
    cpu['base_clock'] = cpu['base_clock'].astype(float)
    cpu['boost_clock'] = cpu['boost_clock'].astype(float)
    cpu = cpu.drop(columns=['Clock_Frequency'])

    cpu['Process_Size'] = cpu['Process_Size'].str.replace('nm', '', case=False, regex=False).str.strip()
    cpu['Process_Size'] = pd.to_numeric(cpu['Process_Size'], errors='coerce')
    cpu['Process_Size'] = cpu['Process_Size'].astype('Int64')

    cpu['L3_Cache'] = cpu['L3_Cache'].str.replace('MB', '', case=False, regex=False).str.strip()
    cpu['L3_Cache'] = pd.to_numeric(cpu['L3_Cache'], errors='coerce')
    cpu['L3_Cache'] = cpu['L3_Cache'].astype(float)

    cpu['TDP'] = cpu['TDP'].str.replace('W', '', case=False, regex=False).str.strip()
    cpu['TDP'] = pd.to_numeric(cpu['TDP'], errors='coerce')
    cpu['TDP'] = cpu['TDP'].astype(float)
# One hot encoder for CPU: Socket

# Clean GPU


    gpu['Clock Speeds__Base Clock'] = gpu['Clock Speeds__Base Clock'].str.replace('MHz', '', case=False, regex=False).str.strip()
    gpu['Clock Speeds__Base Clock'] = pd.to_numeric(gpu['Clock Speeds__Base Clock'], errors='coerce')
    gpu['Clock Speeds__Base Clock'] = gpu['Clock Speeds__Base Clock'].astype(float)

    gpu['Clock Speeds__Boost Clock'] = gpu['Clock Speeds__Boost Clock'].str.replace('MHz', '', case=False, regex=False).str.strip()
    gpu['Clock Speeds__Boost Clock'] = pd.to_numeric(gpu['Clock Speeds__Boost Clock'], errors='coerce')
    gpu['Clock Speeds__Boost Clock'] = gpu['Clock Speeds__Boost Clock'].astype(float)

# The memory-size values in the matching GPU CSV are all in GB.
    gpu['Memory__Memory Size'] = gpu['Memory__Memory Size'].str.replace('GB', '', case=False, regex=False).str.strip()
    gpu['Memory__Memory Size'] = gpu['Memory__Memory Size'].str.extract(r'(\d+\.?\d*)', expand=False)
    gpu['Memory__Memory Size'] = pd.to_numeric(gpu['Memory__Memory Size'], errors='coerce')
    gpu['Memory__Memory Size'] = gpu['Memory__Memory Size'].astype(float)

    gpu['Memory__Memory Bus'] = gpu['Memory__Memory Bus'].str.replace('bit', '', case=False, regex=False).str.strip()
    gpu['Memory__Memory Bus'] = gpu['Memory__Memory Bus'].str.extract(r'(\d+)', expand=False)
    gpu['Memory__Memory Bus'] = pd.to_numeric(gpu['Memory__Memory Bus'], errors='coerce')
    gpu['Memory__Memory Bus'] = gpu['Memory__Memory Bus'].astype('Int64')

    is_tb = gpu['Memory__Bandwidth'].str.contains('TB/s', case=False, na=False)
    gpu['Memory__Bandwidth'] = gpu['Memory__Bandwidth'].str.replace('GB/s', '', case=False, regex=False).str.strip()
    gpu['Memory__Bandwidth'] = gpu['Memory__Bandwidth'].str.replace('TB/s', '', case=False, regex=False).str.strip()
    gpu['Memory__Bandwidth'] = gpu['Memory__Bandwidth'].str.extract(r'(\d+\.?\d*)', expand=False)
    gpu['Memory__Bandwidth'] = pd.to_numeric(gpu['Memory__Bandwidth'], errors='coerce')
    gpu['Memory__Bandwidth'] = np.where(
    is_tb,
    gpu['Memory__Bandwidth'] * 1000,
    gpu['Memory__Bandwidth']
)

    gpu['Board Design__TDP'] = pd.to_numeric(
    gpu['Board Design__TDP'].str.replace('W', '', case=False, regex=False).str.strip(),
    errors='coerce'
)
    gpu['Board Design__TDP'] = gpu['Board Design__TDP'].astype(float)

    parts = gpu['Top__CORES'].astype(str).str.split('x', n=1, expand=True).reindex(columns=[0, 1])
    cores = pd.to_numeric(parts[0].str.strip(), errors='coerce')
    multiplier = pd.to_numeric(parts[1].astype('string').str.strip(), errors='coerce').fillna(1)
    gpu['Top__CORES'] = (cores * multiplier).astype('Int64')

    gpu['Render Config__Shading Units'] = pd.to_numeric(gpu['Render Config__Shading Units'], errors='coerce')
    gpu['Render Config__RT Cores'] = pd.to_numeric(gpu['Render Config__RT Cores'], errors='coerce')

    gpu['Theoretical Performance__FP32 (float)'] = gpu['Theoretical Performance__FP32 (float)'].str.replace('TFLOPS', '', case=False, regex=False).str.strip()
    gpu['Theoretical Performance__FP32 (float)'] = pd.to_numeric(gpu['Theoretical Performance__FP32 (float)'], errors='coerce')
    gpu['Theoretical Performance__FP32 (float)'] = gpu['Theoretical Performance__FP32 (float)'].astype(float)

# Clean FPS
# One hot encoder for FPS: preset, rt_quality, upscaling, upscaling_quality, engine, game

    dimensions = fps['resolution'].str.split('x', n=1, expand=True).reindex(columns=[0, 1])
    dimensions[0] = pd.to_numeric(dimensions[0], errors='coerce')
    dimensions[1] = pd.to_numeric(dimensions[1], errors='coerce')
    fps['pixel_count'] = dimensions[0] * dimensions[1]

    fps['ray_tracing'] = fps['ray_tracing'].astype(int)
    fps['rt_quality'] = fps['rt_quality'].fillna('None')
    fps['upscaling'] = fps['upscaling'].fillna('None')
    fps['upscaling_quality'] = fps['upscaling_quality'].fillna('None')
    fps['avg_fps'] = pd.to_numeric(fps['avg_fps'], errors='coerce')

    merge = fps.merge(cpu, on='cpu_key', how='left', validate='many_to_one')
    merge = merge.merge(gpu, on='gpu_key', how='left', validate='many_to_one')

    return merge

    # pd.read_csv("not_a_real_call.csv")

