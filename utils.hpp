#ifndef UTILS_HPP

#define UTILS_HPP
#include <vector>
#include <string>
#include <fstream>
#include <iostream>
#include "NvInfer.h"

#endif // UTILS_HPP

class Logger : public nvinfer1::ILogger
{
public:
    Severity sev = Severity::kINFO;

    Logger(Severity severity = Severity::kINFO)
    {
        sev = severity;
    }

    void log(Severity severity, const char* msg) noexcept override
    {
        // suppress info-level messages
        if (severity <= sev)
            std::cout << msg << std::endl;
    }
};

// Used for validating if a file exists
bool existsFile(const std::string& filename);

// Used for writing engine data to a file
bool writeEngineToFile(const std::string& filename, nvinfer1::IHostMemory* engine_Data);

// Used for writing engine data to a file
std::vector<char> readEngineFromFile(const std::string& filename);

// Used for printing engine details
void informEngineDetails(nvinfer1::ICudaEngine* engine);