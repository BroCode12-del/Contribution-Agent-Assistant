from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer

def prepare_features(df):
    category = [
        'Socket',
        'Graphics Processor__Architecture',
        'Memory__Memory Type',
        'engine',
        'upscaling_quality',
        'upscaling',
        'rt_quality',
        'preset',
        'game'
    ]

    preprocessor = ColumnTransformer(
        transformers=[
            ('categories',
             OneHotEncoder(handle_unknown='ignore'),
             category)
        ],
        remainder=SimpleImputer(strategy='median')
    )

    X = df[[
        'cores',
        'threads',
        'base_clock',
        'boost_clock',
        'Socket',
        'Process_Size',
        'L3_Cache',
        'TDP',
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
        'demand_score',
        'preset',
        'ray_tracing',
        'rt_quality',
        'upscaling',
        'upscaling_quality',
        'engine',
        'game',
        'pixel_count'
    ]].copy()

    y = df['avg_fps'].copy()

    return X, y, preprocessor