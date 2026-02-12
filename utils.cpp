#include "utils.hpp"
#include <vector>
#include <fstream>
#include <NvInfer.h>

// Used for validating if a file exists
bool existsFile(const std::string& filename) {
    std::ifstream File(filename);
    return File.good();
}

// Used for writing engine data to a file
bool writeEngineToFile(const std::string& filename, nvinfer1::IHostMemory* engine_Data) {
    std::ofstream File(filename, std::ios::binary);
    if (!File) return false;
    File.write(reinterpret_cast<const char*>(engine_Data->data()), engine_Data->size());
    return true;
}

std::vector<char> readEngineFromFile(const std::string& filename) {
    std::ifstream File(filename, std::ios::binary);
    if (!File) return {};
    File.seekg(0, std::ios::end);
    size_t Size = File.tellg();
    File.seekg(0, std::ios::beg);
    std::vector<char> Buffer(Size);
    File.read(Buffer.data(), Size);
    return Buffer;
}

// Used for printing engine details
void informEngineDetails(nvinfer1::ICudaEngine* engine) {
    std::cout << "Engine created with " << engine->getNbIOTensors() << " bindings." << std::endl;
    for (int I = 0; I < engine->getNbIOTensors(); ++I) {
        const char* TensorName = engine->getIOTensorName(I);
        nvinfer1::TensorIOMode IoMode = engine->getTensorIOMode(TensorName); // 0 None, 1 Input, 2 Output
        nvinfer1::Dims Dims = engine->getTensorShape(TensorName);
        nvinfer1::DataType DataType = engine->getTensorDataType(TensorName);
        std::cout << "Binding " << I << ": " << TensorName << " | Mode: "
                  << (IoMode == nvinfer1::TensorIOMode::kINPUT ? "Input" :
                      IoMode == nvinfer1::TensorIOMode::kOUTPUT ? "Output" : "None")
                  << " | Dims: ";
        for (int J = 0; J < Dims.nbDims; ++J) {
            std::cout << Dims.d[J] << (J < Dims.nbDims - 1 ? "x" : "");
        }
        std::cout << " | DataType: ";
        switch (DataType) {
            case nvinfer1::DataType::kFLOAT : std::cout << "FLOAT32"; break;
            case nvinfer1::DataType::kHALF  : std::cout << "FLOAT16"; break;
            case nvinfer1::DataType::kINT8  : std::cout << "INT8"; break;
            case nvinfer1::DataType::kINT32 : std::cout << "INT32"; break;
            case nvinfer1::DataType::kBOOL  : std::cout << "BOOL"; break;
            case nvinfer1::DataType::kUINT8 : std::cout << "UINT8"; break;
            case nvinfer1::DataType::kFP8   : std::cout << "FLOAT8"; break;
            case nvinfer1::DataType::kBF16  : std::cout << "BRAINFLOAT16"; break;
            case nvinfer1::DataType::kINT64 : std::cout << "INT64"; break;
            case nvinfer1::DataType::kINT4  : std::cout << "INT4"; break;
        }
        std::cout << std::endl;
    }
}
    