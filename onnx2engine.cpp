#include <iostream>
#include <NvInfer.h>
#include <NvOnnxParser.h>

#include "utils.hpp"

using namespace nvinfer1;
using namespace nvonnxparser;

int main(int argc, char** argv) {
    if (argc != 4) {
        std::cerr << "usage: " << argv[0] << " <ONNX_file_path> <TRT_file_name> <IMGSZ>" << std::endl;
        return -1;
    }

    const char* OnnxModelFile = argv[1];
    const char* EngineModelFile = argv[2];
    const int Imgsz = std::atoi(argv[3]);
    Logger logger = Logger(ILogger::Severity::kVERBOSE);

    if (existsFile(EngineModelFile)) {
        std::cout << "Engine file " << EngineModelFile << " already exists. Remove it to create a new one." << std::endl;
        std::vector<char> buffer = readEngineFromFile(EngineModelFile);
        if (buffer.empty()) {
            std::cerr << "Failed to read existing engine file." << std::endl;
        }
        else {
            IRuntime* runtime = createInferRuntime(logger);
            ICudaEngine* engine = runtime->deserializeCudaEngine(buffer.data(), buffer.size());
            informEngineDetails(engine);
            return 0;
        }
    }

    auto flag = 1U << static_cast<uint32_t>(NetworkDefinitionCreationFlag::kEXPLICIT_BATCH);

    IBuilder* builder = createInferBuilder(logger);
    INetworkDefinition* network = builder->createNetworkV2(flag);
    
    IParser* parser = createParser(*network, logger);
    parser->parseFromFile(OnnxModelFile, static_cast<int32_t>(ILogger::Severity::kINFO));
    for (int32_t i = 0; i < parser->getNbErrors(); ++i)
    {
        std::cout << parser->getError(i)->desc() << std::endl;
    }
    
    IBuilderConfig* config = builder->createBuilderConfig();

    if (builder->platformHasFastFp16())
    {
        config->setFlag(BuilderFlag::kFP16);
        std::cout << "FP16 supported" << std::endl;
    }
    else
    {
        std::cout << "FP16 not supported" << std::endl;
    }
    
    IOptimizationProfile* profile = builder->createOptimizationProfile();
    ITensor* inputTensor = network->getInput(0);
    Dims4 minDims{1, 3, Imgsz, Imgsz};
    Dims4 optDims{1, 3, Imgsz, Imgsz};
    Dims4 maxDims{1, 3, Imgsz, Imgsz};
    profile->setDimensions(inputTensor->getName(), OptProfileSelector::kMIN, minDims);
    profile->setDimensions(inputTensor->getName(), OptProfileSelector::kOPT, optDims);
    profile->setDimensions(inputTensor->getName(), OptProfileSelector::kMAX, maxDims);
    config->addOptimizationProfile(profile);
    config->setMemoryPoolLimit(MemoryPoolType::kWORKSPACE, 1ULL<<33);

    IHostMemory* serializedModel = builder->buildSerializedNetwork(*network, *config);
    writeEngineToFile(EngineModelFile, serializedModel);

    IRuntime* runtime = createInferRuntime(logger);

    ICudaEngine* engine = runtime->deserializeCudaEngine(serializedModel->data(), serializedModel->size());
    
    informEngineDetails(engine);
    return 0;
}
