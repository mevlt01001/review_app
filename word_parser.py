import os
import json
import argparse
from clang import cindex

import collections.abc
import collections
if not hasattr(collections, 'Iterable'):
    collections.Iterable = collections.abc.Iterable

from spiral import ronin

DEFAULT_INCLUDE_PATHS = ["/usr/include/c++/11", 
                         "/usr/include/x86_64-linux-gnu/c++/11", 
                         "/usr/include",
                         "/opt/nvidia/deepstream/deepstream-7.1/sources/includes",
                         ]

OPTIONS = {
    'var': ['readability-identifier-naming.VariableCase', cindex.CursorKind.VAR_DECL],
    'func': ['readability-identifier-naming.FunctionCase', cindex.CursorKind.FUNCTION_DECL],
    'cls': ['readability-identifier-naming.ClassCase', cindex.CursorKind.CLASS_DECL]
}

def parse_word(variable: str) -> list[str]:
    """
    Parse a variable name into subwords using NLP. ("hellowolrd" -> "hello_world")
    """
    split_result = ronin.split(variable)
    parsed_dec = ""
    for word in split_result:
        parsed_dec += word + "_"
    # print(f"Parsed '{variable}' into: {parsed_dec[:-1]}")
    return parsed_dec[:-1]

def read_file(file_path: str) -> str:
    with open(file_path, 'r') as file:
        content = file.read()
    return content

def get_function_names_with_clang(file_path, include_paths, options):
    index = cindex.Index.create()
    args = [f'-I{path}' for path in include_paths]
    tu = index.parse(file_path, args=args)
    function_names = dict()

    for cursor in tu.cursor.walk_preorder():
        # Eğer bu bir fonksiyon tanımlaması ise
        if not str(cursor.location.file).startswith("/"):
                
                if any(cursor.kind == OPTIONS[opt][1] for opt in options.keys()):

                    name = cursor.spelling
                    location = cursor.location.file
                    
                    split_result = ronin.split(name)
                    parsed_dec = ""
                    for word in split_result:
                        parsed_dec += word + "_"
                    # print(f"Parsed '{variable}' into: {parsed_dec[:-1]}")
                    parsed_name=parsed_dec[:-1]
                    function_names[(str(name), str(location))] = parsed_name
                
    return function_names

def update_context_with_parsed_names(FuncName_Path_ParsedName):
    path_contex = dict()

    for (func, path), new_name in FuncName_Path_ParsedName.items():
        context = read_file(path)
        path_contex[path] = context

    for path, content in path_contex.items():
        for (func, pth), new_name in FuncName_Path_ParsedName.items():
            if pth == path:
                parsed_func_name = ''.join(new_name)
                content = content.replace(func, parsed_func_name)
                print(f"Replaced {func} with {new_name} in file {path}")
        with open(path, 'w') as file:
            file.write(content)

def check_options_parser(options:dict):
    CheckOptions=[]
    for opt, value in options.items():
        if opt not in OPTIONS.keys():
            raise ValueError(f"Invalid option key: {opt}. Valid keys are: {list(OPTIONS.keys())}")
        option_entry = {'key': OPTIONS[opt][0], 'value': value}
        CheckOptions.append(option_entry)
    return CheckOptions

if __name__ == "__main__":
    #args: --files --config-file, --header-filter, --include-paths,
    parser = argparse.ArgumentParser(description="Parse a word into subwords using Ronin.")
    parser.add_argument("--src", type=str, default="./", help="Source directory containing C/C++ files.")
    parser.add_argument("--include", type=str, default="./", help="Include path for header files.")
    parser.add_argument("--config", type=json.loads, default={'var':'CamelCase', 'func':'camelBack', 'cls':'UPPER_CASE'}, help="Configuration for naming conventions in JSON format.")
    parser.add_argument("--include-paths", type=str, default=None, help="Additional include paths separated by spaces.")
    args = parser.parse_args()

    include_paths = DEFAULT_INCLUDE_PATHS+[args.include] if args.include_paths is None else args.include_paths.split()+[args.include]

    CheckOptions = check_options_parser(args.config)

    files = [f for f in os.listdir(args.src) if f.endswith(".cpp") or f.endswith(".h") or f.endswith(".hpp") or f.endswith(".c")]

    for idx, file in enumerate(files):
        path = os.path.join(args.src, file)
        FuncName_Path_ParsedName = get_function_names_with_clang(path, include_paths, args.config)
        update_context_with_parsed_names(FuncName_Path_ParsedName)

    checks = {
        "Checks": "readability-identifier-naming",
        "CheckOptions": CheckOptions
    }

    inculde_flags = " ".join([f"-I{p}" for p in include_paths])
    
    checks = json.dumps(checks)
    command = (
        f"clang-tidy "
        f"-config='{checks}' "
        f"{os.path.join(args.src, '*.cpp')} "
        f"-fix-errors "
        f"--header-filter=\".*{args.include}.*\.(h|hpp)\" "
        f"-- {inculde_flags}"
    )

    os.system(command)
    print(f"RUNNED COMMAND:\n {command}")
