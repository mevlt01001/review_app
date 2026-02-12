#!/bin/bash

ENV_NAME="review-app"
LIB_PATH="$(pwd)/app.py"

sudo apt install curl

# --- 1. MINICONDA KONTROL VE KURULUM ---
if ! command -v conda &> /dev/null; then
    echo "Conda bulunamadı. Miniconda kuruluyor..."
    # Geçici dizine indir
    MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"
    curl -O $MINICONDA_URL
    bash Miniconda3-latest-Linux-x86_64.sh -b -p $HOME/miniconda
    
    # Mevcut oturumda aktif et (Yeniden başlatmaya gerek kalmadan)
    export PATH="$HOME/miniconda/bin:$PATH"
    source "$HOME/miniconda/etc/profile.d/conda.sh"
    conda init bash
    echo "Miniconda başarıyla kuruldu."
else
    echo "Conda zaten yüklü, devam ediliyor..."
    # Mevcut conda'yı script içinde kullanılabilir hale getir
    source "$(conda info --base)/etc/profile.d/conda.sh"
fi

# --- 2. DEĞİŞKENLERİ TANIMLA ---
# (Conda kurulduktan sonra yolları almak daha güvenli)
CONDA_BASE=$(conda info --base)
PIP_PATH="$CONDA_BASE/envs/$ENV_NAME/bin/pip"
PYTHON_PATH="$CONDA_BASE/envs/$ENV_NAME/bin/python"
ALIAS_CMD="alias review-app='$PYTHON_PATH $LIB_PATH'"

# --- 3. ENVIRONMENT İŞLEMLERİ ---
if conda info --envs | grep -q "$ENV_NAME"; then
    echo "'$ENV_NAME' zaten mevcut."
else
    echo "'$ENV_NAME' oluşturuluyor..."
    conda create -n "$ENV_NAME" python=3.10 -y
fi

# --- 4. SİSTEM BAĞIMLILIKLARI VE PIP ---
sudo apt update
sudo apt install libclang-dev clang -y

# Env içindeki pip ve paketler
$PIP_PATH install --upgrade pip
$PIP_PATH install git+https://github.com/casics/spiral.git clang

# --- 5. ALIAS VE SONUÇ ---
# Tekrar tekrar eklememek için kontrol ekleyelim
if ! grep -q "alias review-app=" ~/.bashrc; then
    echo -e "\n# review-app tool\n$ALIAS_CMD" >> ~/.bashrc
    echo "Alias ~/.bashrc dosyasına eklendi."
fi

echo "------------------------------------------"
echo "Kurulum Tamamlandı!"
echo "Komut: review-app"
echo "------------------------------------------"
