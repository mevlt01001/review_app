#!/bin/bash
set -e

ENV_NAME="review-app"
APP_PATH="$(pwd)/app.py"
MINICONDA_PATH="$HOME/miniconda3"


if ! command -v conda &> /dev/null; then
    echo "Conda not found, please setup..."
    echo "Installation instructures inside link = https://www.anaconda.com/docs/getting-started/miniconda/install"
    ARCH=$(uname -m)
    echo "Detected, using $ARCH architecture. Please concern it"
    exit
else
    sudo apt update && sudo apt install -y git curl wget libclang-dev clang
    echo "Packages completed."
    
    conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
    conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
    
    if conda info --envs | grep -q "$ENV_NAME"; then
        echo "Environment '$ENV_NAME' already exists, updating..."
    else
        echo "Environment '$ENV_NAME' creating..."
        conda create -n "$ENV_NAME" python=3.10 -y
    fi
fi

CONDA_BASE=$(conda info --base)
PIP_PATH="$CONDA_BASE/envs/$ENV_NAME/bin/pip"
PYTHON_PATH="$CONDA_BASE/envs/$ENV_NAME/bin/python"
ALIAS_CMD="alias review-app='$PYTHON_PATH $APP_PATH'" 

echo "CONDA_BASE: $CONDA_BASE"
echo "PIP_PATH: $PIP_PATH"
echo "PYTHON_PATH: $PYTHON_PATH"
echo "ALIAS_CMD: $ALIAS_CMD"

# Environment'ı aktif et ve paketleri kur

echo "$ENV_NAME packages creating..."
CLANG_VERSION=$(clang --version | grep -oP 'clang version \K[0-9]+\.[0-9]+' | head -1)

if [ -z "$CLANG_VERSION" ]; then
    echo "❌ clang sürümü tespit edilemedi."
    exit 1
fi

conda run -n "$ENV_NAME" pip uninstall clang -y
conda run -n "$ENV_NAME" pip install --upgrade pip
conda run -n "$ENV_NAME" pip install git+https://github.com/casics/spiral.git clang=="$CLANG_VERSION"

# --- 4. ALIAS VE YAPILANDIRMA ---
# Dinamik path belirleme

if ! grep -q "alias review-app=" ~/.bashrc; then
    echo -e "\n# review-app tool\n$ALIAS_CMD" >> ~/.bashrc
    echo "Alias ~/.bashrc dosyasına eklendi."
else
    # Eğer alias varsa ama path değiştiyse güncelle
    sed -i "/alias review-app=/c\\$ALIAS_CMD" ~/.bashrc
    echo "Alias güncellendi."
fi

echo "------------------------------------------"
echo "Kurulum Tamamlandı!"
echo "Yeni komutu kullanmak için:"
echo "source ~/.bashrc"
echo "review-app"
echo "------------------------------------------"
